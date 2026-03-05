# 智信贷配 🏦

> AI驱动的银行贷款产品智能匹配平台  
> 50款2026贴息产品 · 实时征信分析 · 秒级匹配

---

## ⚡ 一键启动（推荐）

```bash
# 1. 进入项目目录
cd zhixindaipei

# 2. 给脚本加权限（只需第一次）
chmod +x start.sh

# 3. 一键启动前端 + 后端
bash start.sh
```

脚本会自动：
- 检查 Node.js 和 Python3
- 创建 Python 虚拟环境
- 安装所有依赖
- 启动后端（8000端口）+ 前端（5173端口）
- 自动打开浏览器

---

## 📁 项目结构

```
zhixindaipei/
├── start.sh                    ← 一键启动脚本
├── backend/
│   ├── main.py                 ← FastAPI 接口
│   ├── match_engine.py         ← 征信分析 + 匹配引擎
│   ├── loan_products.csv       ← 50款产品数据库
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx             ← 主界面
│   │   ├── main.tsx
│   │   └── index.css
│   ├── package.json
│   └── vite.config.ts
└── tests/
    ├── test_sample_1.json      ← 测试用征信文件
    ├── test_sample_2.json
    └── ...
```

---

## 🔧 手动启动（如一键脚本有问题）

**后端：**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**前端（新开 Terminal）：**
```bash
cd frontend
npm install
npm run dev
```

---

## 🌐 访问地址

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

---

## 🧪 测试

直接在界面上传 `tests/test_sample_1.json`（优质征信）查看效果。

---

## 📡 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/analyze` | 上传征信报告，返回信用分+匹配产品 |
| GET  | `/products` | 查询产品库 |
| GET  | `/products/stats` | 数据库统计 |

---

## ⚠️ 注意事项

1. 需要 **Node.js 18+** 和 **Python 3.9+**
2. 首次启动需要下载依赖，约需 1-2 分钟
3. 利率/额度以各银行官方最新公告为准，本系统数据仅供参考
