#!/bin/bash
# 阿里云函数计算后端部署包打包脚本

set -e

echo "=== 智信贷配后端部署包打包脚本 ==="
echo ""

PROJECT_DIR="/Users/andy/Desktop/zhixindaipei/backend"
DEPLOY_DIR="/tmp/zhixindaipei-deploy"
OUTPUT_FILE="$HOME/zhixindaipei-api.zip"

echo "1. 清理旧文件..."
rm -rf "$DEPLOY_DIR"
rm -f "$OUTPUT_FILE"
mkdir -p "$DEPLOY_DIR"

echo "2. 复制后端代码..."
cd "$PROJECT_DIR"
cp -r *.py *.csv requirements.txt "$DEPLOY_DIR/"

echo "3. 安装依赖（这可能需要几分钟）..."
cd "$DEPLOY_DIR"

# 安装所有依赖到本地目录
pip3 install -r requirements.txt -t . --quiet 2>&1 | grep -v "WARNING: You are using pip" || true

echo "4. 清理不必要的文件..."
# 删除测试文件和缓存以减小体积
find . -type d -name "test*" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
rm -rf *.pyc 2>/dev/null || true

echo "5. 打包..."
zip -r "$OUTPUT_FILE" . -q

echo ""
echo "=== 打包完成 ==="
echo "文件位置: $OUTPUT_FILE"
echo "文件大小: $(du -h "$OUTPUT_FILE" | cut -f1)"
echo ""
echo "使用方法:"
echo "1. 登录阿里云函数计算控制台: https://fc.console.aliyun.com/"
echo "2. 创建服务: zhixindaipei-service"
echo "3. 创建函数:"
echo "   - 函数名称: zhixindaipei-api"
echo "   - 运行环境: Python 3.10"
echo "   - 函数入口: main.handler"
echo "   - 上传此 zip 文件"
echo "4. 创建 HTTP 触发器，允许匿名访问"
