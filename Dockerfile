# 多阶段构建：先构建前端，再打包到 Python 镜像
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --only=production

COPY frontend/ ./
RUN npm run build

# Python 后端镜像
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ ./backend/

# 复制前端构建结果到静态文件目录
COPY --from=frontend-builder /app/frontend/dist ./static/

# 设置工作目录为 backend
WORKDIR /app/backend

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]