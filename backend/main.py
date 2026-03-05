"""
智信贷配 FastAPI 后端
启动：uvicorn main:app --reload --port 8000
"""

import io
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from match_engine import analyze_credit_report, match_products

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

CSV_PATH = Path(__file__).parent / "loan_products.csv"

app = FastAPI(
    title="智信贷配 API",
    description="银行贷款产品数据库 + 征信分析匹配引擎",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 生产环境改为具体域名
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_products() -> pd.DataFrame:
    if not CSV_PATH.exists():
        raise HTTPException(503, f"产品数据库不存在: {CSV_PATH}")
    return pd.read_csv(CSV_PATH, encoding="utf-8-sig")


@app.get("/", tags=["健康检查"])
def root():
    return {
        "status": "ok",
        "service": "智信贷配 API v2.0",
        "time": datetime.now().isoformat(),
        "products_loaded": len(load_products()),
    }


@app.post("/analyze", tags=["核心分析"])
async def analyze(file: UploadFile = File(...)):
    """
    上传征信报告（JSON / PDF / TXT），返回：
    - credit_health_score: 信用健康分 (0-100)
    - risk_level: 风险等级
    - detailed_explanation: 详细解读
    - matches: 匹配产品列表（含 match_score 和 max_amount，均来自真实计算）
    """
    raw = await file.read()

    # PDF 提取文字
    if file.filename and file.filename.lower().endswith(".pdf"):
        try:
            from pdfminer.high_level import extract_text
            content = extract_text(io.BytesIO(raw))
        except ImportError:
            content = raw.decode("utf-8", errors="ignore")
    else:
        content = raw.decode("utf-8", errors="ignore")

    # 解析征信 + 计算信用分
    features = analyze_credit_report(content)
    score = features["credit_health_score"]
    level = features["risk_level"]
    explanation = features["detailed_explanation"]

    # 匹配产品
    df = load_products()
    matches = match_products(features, df)

    return {
        "credit_health_score": score,
        "risk_level": level,
        "detailed_explanation": explanation,
        "matches": matches,
    }


@app.get("/products", tags=["产品数据库"])
def get_products(
    institution_type: Optional[str] = None,
    loan_type: Optional[str] = None,
    limit: int = 50,
):
    """查询产品库，支持按机构类型/贷款类型筛选"""
    df = load_products()
    if institution_type:
        df = df[df["机构类型"] == institution_type]
    if loan_type:
        df = df[df["贷款类型"] == loan_type]
    return df.head(limit).to_dict(orient="records")


@app.get("/products/stats", tags=["产品数据库"])
def get_stats():
    """数据库统计信息"""
    df = load_products()
    return {
        "total_products": len(df),
        "institutions": int(df["机构名称"].nunique()),
        "institution_types": df["机构类型"].value_counts().to_dict(),
        "loan_types": df["贷款类型"].value_counts().to_dict(),
        "last_updated": df["更新日期"].max() if "更新日期" in df.columns else None,
    }
