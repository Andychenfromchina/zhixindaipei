#!/bin/bash
# ╔══════════════════════════════════════════════════╗
# ║         智信贷配 一键启动脚本 (macOS)              ║
# ║   使用方法: 双击运行 或 bash start.sh              ║
# ╚══════════════════════════════════════════════════╝

set -e

# 颜色
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       智信贷配 启动中...              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# ── 检查依赖 ──────────────────────────────────────────

echo -e "${YELLOW}[1/5] 检查系统依赖...${NC}"

# 检查 Node.js
if ! command -v node &> /dev/null; then
  echo -e "${RED}❌ 未找到 Node.js，请先安装: https://nodejs.org${NC}"
  exit 1
fi
echo -e "${GREEN}✅ Node.js $(node -v)${NC}"

# 检查 Python3
if ! command -v python3 &> /dev/null; then
  echo -e "${RED}❌ 未找到 Python3，请先安装: https://www.python.org${NC}"
  exit 1
fi
echo -e "${GREEN}✅ Python $(python3 --version)${NC}"

# 检查 pip3
if ! command -v pip3 &> /dev/null; then
  echo -e "${RED}❌ 未找到 pip3${NC}"
  exit 1
fi

# ── 安装后端依赖 ──────────────────────────────────────

echo ""
echo -e "${YELLOW}[2/5] 安装后端 Python 依赖...${NC}"
cd "$BACKEND_DIR"

# 创建虚拟环境（如不存在）
if [ ! -d "venv" ]; then
  python3 -m venv venv
  echo -e "${GREEN}✅ 虚拟环境已创建${NC}"
fi

source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet fastapi "uvicorn[standard]" python-multipart pandas pdfminer.six

echo -e "${GREEN}✅ 后端依赖安装完成${NC}"

# ── 安装前端依赖 ──────────────────────────────────────

echo ""
echo -e "${YELLOW}[3/5] 安装前端 Node 依赖...${NC}"
cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
  npm install --silent
fi
echo -e "${GREEN}✅ 前端依赖安装完成${NC}"

# ── 创建前端环境变量 ──────────────────────────────────

echo ""
echo -e "${YELLOW}[4/5] 配置环境变量...${NC}"
if [ ! -f "$FRONTEND_DIR/.env" ]; then
  echo "VITE_API_URL=http://localhost:8000" > "$FRONTEND_DIR/.env"
  echo -e "${GREEN}✅ .env 文件已创建${NC}"
else
  echo -e "${GREEN}✅ .env 已存在，跳过${NC}"
fi

# ── 启动服务 ──────────────────────────────────────────

echo ""
echo -e "${YELLOW}[5/5] 启动前后端服务...${NC}"
echo ""

# 启动后端（后台）
cd "$BACKEND_DIR"
source venv/bin/activate
echo -e "${CYAN}🚀 启动后端 (http://localhost:8000)...${NC}"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

sleep 2

# 检查后端是否启动成功
if curl -s http://localhost:8000/ > /dev/null 2>&1; then
  echo -e "${GREEN}✅ 后端启动成功${NC}"
else
  echo -e "${YELLOW}⏳ 后端正在启动中...${NC}"
fi

# 启动前端（后台）
cd "$FRONTEND_DIR"
echo -e "${CYAN}🚀 启动前端 (http://localhost:5173)...${NC}"
npm run dev &
FRONTEND_PID=$!

sleep 3

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ 智信贷配 启动成功！                  ║${NC}"
echo -e "${GREEN}║                                          ║${NC}"
echo -e "${GREEN}║   前端: http://localhost:5173             ║${NC}"
echo -e "${GREEN}║   后端: http://localhost:8000             ║${NC}"
echo -e "${GREEN}║   API文档: http://localhost:8000/docs     ║${NC}"
echo -e "${GREEN}║                                          ║${NC}"
echo -e "${GREEN}║   测试文件: tests/test_sample_1.json      ║${NC}"
echo -e "${GREEN}║                                          ║${NC}"
echo -e "${GREEN}║   按 Ctrl+C 停止所有服务                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""

# 自动打开浏览器
sleep 2
open http://localhost:5173

# 等待用户退出
trap "echo ''; echo -e '${YELLOW}正在停止服务...${NC}'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo -e '${GREEN}✅ 已停止${NC}'; exit" INT
wait
