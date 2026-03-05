#!/bin/bash
# 智信贷配一键部署脚本
# 使用方法: bash deploy.sh

set -e

echo "═══════════════════════════════════════════"
echo "   智信贷配 - 自动部署脚本"
echo "═══════════════════════════════════════════"
echo ""

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 检查依赖
echo -e "${YELLOW}[1/4] 检查依赖...${NC}"

if ! command -v node &> /dev/null; then
    echo "❌ 需要安装 Node.js"
    echo "   下载地址: https://nodejs.org"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ 需要安装 Python3"
    exit 1
fi

echo -e "${GREEN}✅ Node.js $(node -v)${NC}"
echo -e "${GREEN}✅ Python $(python3 --version)${NC}"

# 构建前端
echo ""
echo -e "${YELLOW}[2/4] 构建前端...${NC}"
cd frontend
npm install --silent 2>/dev/null || true
npm run build
echo -e "${GREEN}✅ 前端构建完成${NC}"
cd ..

# 检查 Vercel CLI
echo ""
echo -e "${YELLOW}[3/4] 检查 Vercel CLI...${NC}"
if ! command -v vercel &> /dev/null; then
    echo "正在安装 Vercel CLI..."
    npm install -g vercel
fi
echo -e "${GREEN}✅ Vercel CLI 已安装${NC}"

# 检查 Render CLI
echo ""
echo -e "${YELLOW}[4/4] 检查 Render CLI...${NC}"
if ! command -v render &> /dev/null; then
    echo "ℹ️  Render CLI 未安装，将使用 Web 界面部署"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "   准备就绪！请选择部署方式:"
echo "═══════════════════════════════════════════"
echo ""
echo "方式 A: 自动部署到 Vercel (前端)"
echo "  运行: vercel --prod"
echo ""
echo "方式 B: 手动部署到 Render (后端)"
echo "  1. 访问 https://dashboard.render.com"
echo "  2. 点击 'New +' → 'Web Service'"
echo "  3. 选择 GitHub 仓库: Andychenfromchina/zhixindaipei"
echo "  4. 配置:"
echo "     - Root Directory: backend"
echo "     - Build Command: pip install -r requirements.txt"
echo "     - Start Command: uvicorn main:app --host 0.0.0.0 --port \$PORT"
echo ""
echo "═══════════════════════════════════════════"
echo ""

# 询问是否部署前端
read -p "是否现在部署前端到 Vercel? (y/n): " answer
if [[ $answer == "y" || $answer == "Y" ]]; then
    echo ""
    echo -e "${CYAN}正在部署前端到 Vercel...${NC}"
    cd frontend
    vercel --prod
    echo ""
    echo -e "${GREEN}✅ 前端部署完成!${NC}"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "   部署指南"
echo "═══════════════════════════════════════════"
echo ""
echo "前端部署完成后，请记录 Vercel 分配的域名。"
echo ""
echo "然后访问 Render 部署后端:"
echo "  https://dashboard.render.com"
echo ""
echo "后端部署完成后:"
echo "  1. 复制 Render 的 URL (如 https://xxx.onrender.com)"
echo "  2. 在 Vercel 项目设置中添加环境变量:"
echo "     VITE_API_URL=https://xxx.onrender.com"
echo "  3. 重新部署前端"
echo ""
echo "═══════════════════════════════════════════"