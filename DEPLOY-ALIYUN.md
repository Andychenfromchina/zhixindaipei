# 阿里云部署指南

## 部署架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   用户浏览器     │────→│   阿里云 CDN    │────→│   阿里云 OSS    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              (静态网站托管)
                              
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   用户浏览器     │────→│   HTTP 请求     │────→│  函数计算 FC    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              (API 网关)            (FastAPI)
```

## 前置条件

1. **阿里云账号** - 注册并实名认证
2. **AccessKey** - 在 [RAM 控制台](https://ram.console.aliyun.com/) 创建
3. **安装依赖**:
   - Node.js (v18+)
   - Python (v3.10+)
   - npm/pip

## 快速部署

### 方式一：自动部署（推荐）

```bash
# 1. 配置阿里云凭证
export ALIBABA_CLOUD_ACCESS_KEY_ID=你的AccessKeyID
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=你的AccessKeySecret
export ALIBABA_CLOUD_REGION_ID=cn-hangzhou

# 2. 运行部署脚本
cd /Users/andy/Desktop/zhixindaipei
./deploy-aliyun.sh
```

### 方式二：手动部署

#### 1. 部署前端（OSS + CDN）

```bash
cd frontend
npm install
npm run build

# 创建 Bucket（需要全局唯一名称）
aliyun oss mb oss://zhixindaipei-web-你的后缀 --region cn-hangzhou

# 配置静态网站
aliyun oss put-bucket-website oss://zhixindaipei-web-你的后缀 file://website.json

# 上传文件
ossutil cp -r dist oss://zhixindaipei-web-你的后缀/

# 设置公共读权限
ossutil set-acl oss://zhixindaipei-web-你的后缀/ public-read -r
```

#### 2. 部署后端（函数计算 FC）

```bash
cd backend

# 安装依赖到本地
pip install -r requirements.txt -t .

# 打包
zip -r function.zip . -x "venv/*" "*.pyc" "__pycache__/*"

# 创建服务
aliyun fc3 CreateService --region cn-hangzhou \
    --service-name zhixindaipei-service \
    --body '{"description":"智信贷配后端服务"}'

# 创建函数
aliyun fc3 CreateFunction --region cn-hangzhou \
    --service-name zhixindaipei-service \
    --function-name zhixindaipei-api \
    --body '{
        "functionName": "zhixindaipei-api",
        "runtime": "python3.10",
        "handler": "main.handler",
        "memorySize": 512,
        "timeout": 60,
        "code": {"zipFile": "'$(base64 -i function.zip)'"}
    }'

# 创建 HTTP 触发器
aliyun fc3 CreateTrigger --region cn-hangzhou \
    --service-name zhixindaipei-service \
    --function-name zhixindaipei-api \
    --body '{
        "triggerName": "http-trigger",
        "triggerType": "http",
        "triggerConfig": {
            "authType": "anonymous",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        }
    }'
```

## 配置说明

### 前端配置

创建 `frontend/.env.production`:

```
VITE_API_URL=https://zhixindaipei-api.zhixindaipei-service.cn-hangzhou.fcapp.run
```

### 函数计算配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| runtime | python3.10 | Python 版本 |
| handler | main.handler | 入口函数 |
| memorySize | 512 MB | 内存大小 |
| timeout | 60 秒 | 超时时间 |

## 费用估算（每月）

| 服务 | 免费额度 | 超出费用 |
|------|---------|---------|
| OSS 存储 | 5GB 免费 | ¥0.12/GB/月 |
| OSS 流量 | 10GB 免费 | ¥0.24/GB |
| CDN 流量 | 10GB 免费 | ¥0.24/GB |
| 函数计算 | 100万次调用免费 | ¥0.0133/万次 |
| 函数计算内存 | 40万GB-秒免费 | ¥0.000016/GB-秒 |

**估算**: 小流量网站每月基本在免费额度内。

## 监控与日志

```bash
# 查看函数日志
aliyun fc3 GetFunctionLogs --region cn-hangzhou \
    --service-name zhixindaipei-service \
    --function-name zhixindaipei-api

# 查看函数调用指标
aliyun fc3 GetFunctionMetrics --region cn-hangzhou \
    --service-name zhixindaipei-service \
    --function-name zhixindaipei-api
```

## 故障排查

### 问题：前端 404
- 检查 OSS Bucket 静态网站配置
- 确认 index.html 已上传
- 检查 Bucket 访问权限

### 问题：后端 API 超时
- 检查函数计算的 timeout 配置
- 查看函数日志排查代码问题
- 考虑增加 memorySize

### 问题：CORS 错误
- 后端已配置 `allow_origins=["*"]`
- 生产环境建议改为具体域名

## 进阶配置

### 自定义域名

1. **前端**: 在 CDN 控制台添加域名，绑定 OSS Bucket
2. **后端**: 在函数计算控制台添加自定义域名

### HTTPS 配置

- 在 CDN 控制台申请免费 SSL 证书
- 或上传已有证书

### 更新部署

```bash
# 前端更新
npm run build
ossutil cp -r frontend/dist oss://你的bucket/ -f -u

# 后端更新
./deploy-aliyun.sh
```

## 参考文档

- [阿里云 OSS 文档](https://help.aliyun.com/oss)
- [阿里云函数计算文档](https://help.aliyun.com/fc)
- [阿里云 CLI 文档](https://help.aliyun.com/cli)
