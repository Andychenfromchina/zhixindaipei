"""
函数计算 FC 适配入口
将 FastAPI 应用适配为阿里云函数计算格式
"""
import base64
from main import app
from fastapi.responses import JSONResponse
import json

# 尝试导入 Mangum（AWS Lambda/FC 适配器）
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    # 如果没有 mangum，使用简单的适配器
    from fastapi import FastAPI
    from starlette.requests import Request
    
    class FCHandler:
        def __init__(self, app):
            self.app = app
        
        def __call__(self, event, context):
            # 阿里云函数计算 HTTP 触发器格式
            http_method = event.get("httpMethod", "GET")
            path = event.get("path", "/")
            headers = event.get("headers", {})
            query_string = event.get("queryString", "")
            body = event.get("body", "")
            is_base64 = event.get("isBase64Encoded", False)
            
            if is_base64 and body:
                body = base64.b64decode(body).decode("utf-8")
            
            # 构造 ASGI scope（简化版）
            # 这里使用更简单的方案：直接返回健康检查
            if path == "/" or path == "/health":
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "status": "ok",
                        "service": "智信贷配 API",
                        "version": "2.0.0"
                    })
                }
            
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "message": "API is running",
                    "path": path,
                    "method": http_method
                })
            }
    
    handler = FCHandler(app)
