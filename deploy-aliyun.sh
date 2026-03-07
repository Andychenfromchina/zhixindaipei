#!/bin/bash
# 阿里云部署脚本 - 智信贷配

set -e

echo "=== 智信贷配 - 阿里云部署脚本 ==="
echo ""

# 配置变量（请根据实际情况修改）
REGION="cn-hangzhou"                    # 阿里云区域
BUCKET_NAME="zhixindaipei-web-$(date +%s)"  # OSS Bucket 名称（需要全局唯一）
FUNCTION_NAME="zhixindaipei-api"        # 函数计算函数名
SERVICE_NAME="zhixindaipei-service"     # 函数计算服务名

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查阿里云 CLI
if ! command -v aliyun &> /dev/null; then
    echo -e "${YELLOW}正在安装阿里云 CLI...${NC}"
    curl -fsSL https://aliyuncli.alicdn.com/install.sh | bash
    export PATH=$PATH:/usr/local/bin
fi

# 检查是否配置了阿里云凭证
echo "检查阿里云凭证..."
if ! aliyun sts GetCallerIdentity &> /dev/null; then
    echo -e "${RED}错误：阿里云凭证未配置${NC}"
    echo ""
    echo "请执行以下命令之一："
    echo ""
    echo "方式1 - 交互式配置："
    echo "  aliyun configure"
    echo ""
    echo "方式2 - 环境变量（推荐，用于CI/CD）："
    echo "  export ALIBABA_CLOUD_ACCESS_KEY_ID=你的AccessKeyID"
    echo "  export ALIBABA_CLOUD_ACCESS_KEY_SECRET=你的AccessKeySecret"
    echo "  export ALIBABA_CLOUD_REGION_ID=$REGION"
    echo ""
    echo "获取 AccessKey："
    echo "  登录 https://ram.console.aliyun.com/"
    echo "  创建用户 → 获取 AccessKey ID 和 Secret"
    exit 1
fi

echo -e "${GREEN}✓ 阿里云凭证验证通过${NC}"
echo ""

# 获取账号信息
ACCOUNT_ID=$(aliyun sts GetCallerIdentity | grep -o '"AccountId": "[0-9]*"' | cut -d'"' -f4)
echo "当前账号ID: $ACCOUNT_ID"
echo "部署区域: $REGION"
echo ""

# 确认部署
read -p "是否继续部署? (y/N): " confirm
if [[ $confirm != [yY] ]]; then
    echo "已取消部署"
    exit 0
fi

# 步骤1: 构建前端
echo ""
echo -e "${YELLOW}步骤 1/6: 构建前端...${NC}"
cd frontend
npm install
npm run build
cd ..
echo -e "${GREEN}✓ 前端构建完成${NC}"

# 步骤2: 创建 OSS Bucket
echo ""
echo -e "${YELLOW}步骤 2/6: 创建 OSS Bucket...${NC}"
aliyun oss mb oss://${BUCKET_NAME} --region ${REGION} 2>/dev/null || echo "Bucket 已存在或创建中..."

# 配置 Bucket 为静态网站
cat > /tmp/website.json << 'EOF'
{
  "IndexDocument": {"Suffix": "index.html"},
  "ErrorDocument": {"Key": "index.html"}
}
EOF

aliyun oss put-bucket-website oss://${BUCKET_NAME} file:///tmp/website.json --region ${REGION} 2>/dev/null || true
echo -e "${GREEN}✓ OSS Bucket 配置完成${NC}"

# 步骤3: 上传前端文件
echo ""
echo -e "${YELLOW}步骤 3/6: 上传前端文件到 OSS...${NC}"

# 使用 ossutil 上传（更稳定）
if ! command -v ossutil &> /dev/null; then
    curl -o /tmp/ossutil https://gosspublic.alicdn.com/ossutil/1.7.15/ossutilmac64
    chmod +x /tmp/ossutil
    OSSUTIL="/tmp/ossutil"
else
    OSSUTIL="ossutil"
fi

# 配置 ossutil
cat > /tmp/.ossutilconfig << EOF
[Credentials]
language=EN
endpoint=oss-${REGION}.aliyuncs.com
EOF

$OSSUTIL cp -r frontend/dist oss://${BUCKET_NAME}/ -f -u --config-file /tmp/.ossutilconfig
echo -e "${GREEN}✓ 前端文件上传完成${NC}"

# 设置文件 ACL
$OSSUTIL set-acl oss://${BUCKET_NAME}/ public-read -r --config-file /tmp/.ossutilconfig
echo -e "${GREEN}✓ 设置文件访问权限完成${NC}"

# 步骤4: 准备后端
echo ""
echo -e "${YELLOW}步骤 4/6: 准备后端部署包...${NC}"
cd backend

# 创建临时目录
DEPLOY_DIR=$(mktemp -d)
cp -r . "$DEPLOY_DIR/"
cd "$DEPLOY_DIR"

# 安装依赖（函数计算使用）
pip install -r requirements.txt -q -t . 2>/dev/null || pip3 install -r requirements.txt -q -t .

# 打包
zip -r /tmp/function.zip . -x "venv/*" "*.pyc" "__pycache__/*" ".git/*" "*.egg-info/*" > /dev/null
echo -e "${GREEN}✓ 后端打包完成 ($(du -h /tmp/function.zip | cut -f1))${NC}"

# 步骤5: 创建函数计算服务
echo ""
echo -e "${YELLOW}步骤 5/6: 创建函数计算服务...${NC}"

# 创建服务
aliyun fc3 CreateService --region ${REGION} \
    --service-name ${SERVICE_NAME} \
    --body '{"description":"智信贷配后端服务"}' 2>/dev/null || echo "服务已存在"

# 创建函数
FUNCTION_BODY=$(cat << EOF
{
  "functionName": "${FUNCTION_NAME}",
  "runtime": "python3.10",
  "handler": "main.handler",
  "memorySize": 512,
  "timeout": 60,
  "environmentVariables": {},
  "code": {"zipFile": "$(base64 -i /tmp/function.zip)"}
}
EOF
)

echo "正在部署函数..."
aliyun fc3 CreateFunction --region ${REGION} \
    --service-name ${SERVICE_NAME} \
    --body "$FUNCTION_BODY" 2>/dev/null || \
aliyun fc3 UpdateFunction --region ${REGION} \
    --service-name ${SERVICE_NAME} \
    --function-name ${FUNCTION_NAME} \
    --code "zipFile=$(base64 -i /tmp/function.zip)"

echo -e "${GREEN}✓ 函数部署完成${NC}"

# 创建 HTTP 触发器
echo ""
echo -e "${YELLOW}步骤 6/6: 配置 HTTP 触发器...${NC}"

TRIGGER_BODY=$(cat << EOF
{
  "triggerName": "http-trigger",
  "triggerType": "http",
  "triggerConfig": {
    "authType": "anonymous",
    "methods": ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]
  }
}
EOF
)

aliyun fc3 CreateTrigger --region ${REGION} \
    --service-name ${SERVICE_NAME} \
    --function-name ${FUNCTION_NAME} \
    --body "$TRIGGER_BODY" 2>/dev/null || echo "触发器已存在"

echo -e "${GREEN}✓ HTTP 触发器配置完成${NC}"

# 获取函数 URL
FUNCTION_URL="https://${FUNCTION_NAME}.${SERVICE_NAME}.${REGION}.fcapp.run"

# 清理
cd /Users/andy/Desktop/zhixindaipei
rm -rf "$DEPLOY_DIR"

echo ""
echo "========================================"
echo -e "${GREEN}部署完成！${NC}"
echo "========================================"
echo ""
echo -e "${YELLOW}前端访问地址：${NC}"
echo "  http://${BUCKET_NAME}.oss-${REGION}.aliyuncs.com"
echo ""
echo -e "${YELLOW}后端 API 地址：${NC}"
echo "  $FUNCTION_URL"
echo ""
echo -e "${YELLOW}API 测试：${NC}"
echo "  curl $FUNCTION_URL/health"
echo ""
echo "========================================"
echo ""
echo "提示："
echo "1. 如需自定义域名，请配置 CDN 加速"
echo "2. 修改前端 API 地址: frontend/src/api/config.ts"
echo "3. 查看日志: aliyun fc3 GetFunctionLogs --region $REGION --service-name $SERVICE_NAME --function-name $FUNCTION_NAME"
