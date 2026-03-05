# 智信贷配 - 部署指南

## 🚀 部署方案: Vercel(前端) + Render(后端)

---

## 第一步：部署后端 (Render)

### 1. 注册/登录 Render
- 访问 https://render.com
- 使用 GitHub 账号登录

### 2. 创建 PostgreSQL 数据库（如需要）
本应用使用 CSV 文件作为数据源，暂不需要数据库

### 3. 创建 Web Service
1. 点击 **New +** → **Web Service**
2. 连接你的 GitHub 仓库（需要先将代码 push 到 GitHub）
3. 或使用 **Deploy from Git URL**

### 4. 配置参数
- **Name**: `zhixindaipei-api`
- **Runtime**: Python 3
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Plan**: Free

### 5. 环境变量
- `PYTHON_VERSION`: `3.11.0`

### 6. 部署完成
- 等待部署完成，记下你的服务 URL
- 例如: `https://zhixindaipei-api.onrender.com`

---

## 第二步：部署前端 (Vercel)

### 1. 注册/登录 Vercel
- 访问 https://vercel.com
- 使用 GitHub 账号登录

### 2. 导入项目
1. 点击 **Add New...** → **Project**
2. 选择你的 GitHub 仓库

### 3. 配置参数
- **Framework Preset**: Vite
- **Root Directory**: `frontend`
- **Build Command**: `npm run build`
- **Output Directory**: `dist`

### 4. 环境变量
添加以下环境变量：
```
VITE_API_URL=https://zhixindaipei-api.onrender.com
```
（替换为你实际的 Render 后端地址）

### 5. 部署
点击 **Deploy**

---

## 📁 文件结构说明

```
zhixindaipei/
├── frontend/          # React + Vite 前端
│   ├── dist/         # 构建输出目录
│   ├── src/          # 源代码
│   ├── vercel.json   # Vercel 配置
│   └── package.json
├── backend/           # FastAPI 后端
│   ├── main.py       # 主入口
│   ├── match_engine.py
│   ├── loan_products.csv
│   ├── requirements.txt
│   └── render.yaml   # Render 配置
└── README.md
```

---

## ⚠️ 注意事项

### Render 免费版限制
- 15 分钟无活动后会休眠
- 首次访问需要等待唤醒（约 30 秒）

### CORS 配置
后端已配置 `allow_origins=["*"]`，生产环境建议改为具体域名：
```python
allow_origins=["https://你的前端域名.vercel.app"]
```

### 数据文件
`loan_products.csv` 需要随代码一起部署，确保在 backend 目录下

---

## 🔄 更新部署

### 前端更新
```bash
cd frontend
git add .
git commit -m "更新前端"
git push
# Vercel 会自动重新部署
```

### 后端更新
```bash
cd backend
git add .
git commit -m "更新后端"
git push
# Render 会自动重新部署
```

---

## 🆘 故障排查

### 前端无法连接后端
1. 检查 `VITE_API_URL` 环境变量是否正确设置
2. 确认后端服务已启动（访问后端 URL + `/` 查看健康检查）

### 后端启动失败
1. 检查 `requirements.txt` 是否完整
2. 查看 Render 的 Logs 页面

### 构建失败
1. 确保 `vercel.json` 中的 `distDir` 正确
2. 本地先执行 `npm run build` 测试

---

## 📝 替代方案

如果不想使用 GitHub，可以：

### 前端 - 直接上传
1. 本地运行 `npm run build` 生成 dist 文件夹
2. 使用 Vercel CLI: `vercel --prod`
3. 或使用 Netlify Drop 直接拖拽上传 dist 文件夹

### 后端 - Docker 部署
如有自己的服务器，可以使用 Docker 统一部署前后端。

---

祝部署顺利！🎉