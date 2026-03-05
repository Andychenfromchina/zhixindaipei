# 智信贷配 - 快速部署指南

## 📦 项目已准备就绪

项目位置：`~/Desktop/zhixindaipei`

✅ GitHub 仓库: https://github.com/Andychenfromchina/zhixindaipei
✅ 前端已构建完成 (dist/ 文件夹已生成)
✅ 部署配置已创建

---

## 🚀 方式一：一键脚本部署（推荐）

### 1. 打开终端，运行脚本

```bash
cd ~/Desktop/zhixindaipei
bash deploy.sh
```

### 2. 按提示操作
- 脚本会检查依赖并构建项目
- 选择是否部署到 Vercel

---

## 🚀 方式二：手动部署

### 第一步：部署后端到 Render

1. 访问 https://dashboard.render.com
2. 点击 **New +** → **Web Service**
3. 选择 **Build and deploy from a Git repository**
4. 连接 GitHub，选择 `Andychenfromchina/zhixindaipei`
5. 填写配置：

| 配置项 | 值 |
|--------|-----|
| Name | `zhixindaipei-api` |
| Root Directory | `backend` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Plan | Free |

6. 点击 **Create Web Service**
7. 等待部署完成（约 2-3 分钟）
8. 记录你的后端地址，例如：`https://zhixindaipei-api.onrender.com`

---

### 第二步：部署前端到 Vercel

1. 访问 https://vercel.com/new
2. 导入 GitHub 仓库 `Andychenfromchina/zhixindaipei`
3. 配置：

| 配置项 | 值 |
|--------|-----|
| Framework Preset | Vite |
| Root Directory | `frontend` |
| Build Command | `npm run build` |
| Output Directory | `dist` |

4. 展开 **Environment Variables**，添加：
   - `VITE_API_URL` = `https://zhixindaipei-api.onrender.com`
   （替换为你的 Render 地址）

5. 点击 **Deploy**
6. 等待部署完成（约 1-2 分钟）

---

## ✅ 验证部署

### 测试后端
访问：`https://你的render地址/`
应该返回：
```json
{
  "status": "ok",
  "service": "智信贷配 API v2.0",
  ...
}
```

### 测试前端
访问 Vercel 分配的域名，应该能看到智信贷配界面。

### 测试完整功能
1. 上传征信报告（tests/test_sample_1.json）
2. 查看信用分析结果
3. 查看匹配的贷款产品

---

## 🔧 常见问题

### Render 后端休眠
Render 免费版 15 分钟无活动会休眠，首次访问需要等待 30 秒唤醒。

### 前端无法连接后端
1. 检查 `VITE_API_URL` 环境变量是否正确设置
2. 确保后端地址包含 `https://` 前缀
3. 在 Vercel 项目设置中重新添加环境变量并重新部署

### CORS 错误
如果看到 CORS 错误，检查后端 `main.py` 中的 CORS 配置：
```python
allow_origins=["*"]  # 或者改为你的前端域名
```

---

## 📝 文件说明

```
zhixindaipei/
├── frontend/           # React + Vite 前端
│   ├── dist/          # 构建输出（已生成）
│   ├── src/           # 源代码
│   ├── vercel.json    # Vercel 配置
│   └── package.json
├── backend/           # FastAPI 后端
│   ├── main.py        # API 入口
│   ├── match_engine.py
│   ├── loan_products.csv
│   ├── requirements.txt
│   └── render.yaml    # Render 配置
├── tests/             # 测试文件
├── deploy.sh          # 一键部署脚本
└── DEPLOY.md          # 详细部署文档
```

---

## 🆘 需要帮助？

如果在部署过程中遇到问题，请告诉我：
1. 具体的错误信息
2. 进行到哪一步出错
3. 截图（如果有）

我会帮你解决！