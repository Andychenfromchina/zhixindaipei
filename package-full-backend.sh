#!/bin/bash
# 全量后端安装包打包脚本
# 在本地终端执行：bash package-full-backend.sh

set -e

echo "========================================"
echo "  智信贷配 - 全量后端部署包打包"
echo "========================================"
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")/backend" && pwd)"
DEPLOY_DIR="/tmp/zhixindaipei-full-$(date +%s)"
OUTPUT_FILE="$HOME/Desktop/zhixindaipei-api-full.zip"

echo "📁 项目目录: $PROJECT_DIR"
echo "📦 输出文件: $OUTPUT_FILE"
echo ""

echo "🧹 步骤 1/5: 清理旧文件..."
rm -rf "$DEPLOY_DIR"
rm -f "$OUTPUT_FILE"
mkdir -p "$DEPLOY_DIR"

echo "📋 步骤 2/5: 复制后端代码..."
cd "$PROJECT_DIR"
cp -r *.py *.csv requirements.txt "$DEPLOY_DIR/"

echo "⬇️  步骤 3/5: 安装依赖（需要2-3分钟）..."
cd "$DEPLOY_DIR"

# 安装依赖到本地目录
echo "   安装 fastapi..."
pip3 install fastapi python-multipart mangum -t . -q

echo "   安装 pandas..."
pip3 install pandas -t . -q

echo "   安装 pdfminer..."
pip3 install pdfminer.six -t . -q

echo "   安装 uvicorn..."
pip3 install uvicorn -t . -q

echo "🧹 步骤 4/5: 清理不必要的文件..."
# 删除测试文件和缓存以减小体积
find . -type d -name "test*" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

echo "📦 步骤 5/5: 打包..."
zip -r "$OUTPUT_FILE" . -q

echo ""
echo "========================================"
echo "  ✅ 打包完成！"
echo "========================================"
echo ""
echo "📦 文件信息:"
echo "   位置: $OUTPUT_FILE"
echo "   大小: $(du -h "$OUTPUT_FILE" | cut -f1)"
echo ""
echo "🚀 部署到阿里云函数计算:"
echo ""
echo "   1. 登录 https://fc.console.aliyun.com/"
echo "   2. 创建服务: zhixindaipei-service"
echo "   3. 创建函数:"
echo "      - 函数名: zhixindaipei-api"
echo "      - 运行时: Python 3.10"
echo "      - 入口: main.handler"
echo "      - 上传此 ZIP 文件"
echo "   4. 创建 HTTP 触发器（匿名访问）"
echo ""
echo "========================================"
