#!/bin/bash
# 智信贷配 - 修复权限并部署

echo "═══════════════════════════════════════════"
echo "   智信贷配 - 部署准备"
echo "═══════════════════════════════════════════"
echo ""

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# 修复 npm 权限
echo -e "${YELLOW}[1/3] 修复 npm 权限...${NC}"
sudo chown -R $(whoami) ~/.npm 2>/dev/null || echo "可能需要手动运行: sudo chown -R \$(whoami) ~/.npm"

echo ""
echo -e "${YELLOW}[2/3] 安装 Vercel CLI...${NC}"
npm install -g vercel

echo ""
echo -e "${YELLOW}[3/3] 准备完成！${NC}"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo -e "${CYAN}   开始部署${NC}"
echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo ""

cd ~/Desktop/zhixindaipei

# 选项菜单
echo "请选择部署方式:"
echo ""
echo "1) 部署到 Render (后端)"
echo "   运行: render deploy"
echo ""
echo "2) 部署到 Vercel (前端)"
echo "   运行: cd frontend && vercel --prod"
echo ""
echo "3) 使用 Docker 一键部署"
echo "   适合: Fly.io, Railway, 或其他支持 Docker 的平台"
echo ""

read -p "请输入选项 (1/2/3): " choice

case $choice in
  1)
    echo ""
    echo -e "${CYAN}正在部署到 Render...${NC}"
    echo "请确保已安装 Render CLI: npm install -g @render/cli"
    echo "然后运行: render deploy"
    ;;
  2)
    echo ""
    echo -e "${CYAN}正在部署到 Vercel...${NC}"
    cd frontend
    vercel --prod
    ;;
  3)
    echo ""
    echo -e "${CYAN}Docker 部署说明:${NC}"
    echo ""
    echo "1. 构建镜像:"
    echo "   docker build -t zhixindaipei ."
    echo ""
    echo "2. 本地运行:"
    echo "   docker run -p 8000:8000 zhixindaipei"
    echo ""
    echo "3. 推送到 Docker Hub 后可在任何平台部署"
    echo ""
    echo -e "${YELLOW}是否现在构建 Docker 镜像? (y/n)${NC}"
    read -p "> " build_docker
    if [[ $build_docker == "y" || $build_docker == "Y" ]]; then
      cd ~/Desktop/zhixindaipei
      docker build -t zhixindaipei .
      echo -e "${GREEN}✅ Docker 镜像构建完成!${NC}"
    fi
    ;;
  *)
    echo "无效选项"
    ;;
esac

echo ""
echo "═══════════════════════════════════════════"
echo "部署说明已保存到 DEPLOY-FINAL.md"
echo "═══════════════════════════════════════════"