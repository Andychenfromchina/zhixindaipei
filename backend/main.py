import json
import os

# 加载产品数据（不使用 pandas，直接解析 CSV）
def load_products_simple():
    """简单加载 CSV 数据"""
    csv_path = os.path.join(os.path.dirname(__file__), "loan_products.csv")
    products = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) < 2:
                return products
            
            # 解析表头
            headers = lines[0].strip().split(',')
            
            # 解析数据行
            for line in lines[1:101]:  # 最多100条
                values = line.strip().split(',')
                if len(values) >= len(headers):
                    product = {}
                    for i, header in enumerate(headers):
                        product[header] = values[i] if i < len(values) else ""
                    products.append(product)
    except Exception as e:
        print(f"Error loading CSV: {e}")
    
    return products

# ============ 阿里云 FC 入口 ============

def handler(event, context):
    """
    阿里云函数计算 HTTP 触发器入口
    """
    # CORS 响应头 - 必须包含，否则前端无法访问
    cors_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, Accept",
        "Access-Control-Max-Age": "86400"
    }
    
    try:
        # 解析 event（FC 3.0 传入的可能是 bytes 或 JSON 字符串）
        if isinstance(event, bytes):
            event = json.loads(event.decode('utf-8'))
        elif isinstance(event, str):
            event = json.loads(event)
        
        # 获取请求信息
        http_method = event.get("httpMethod", "GET") if isinstance(event, dict) else "GET"
        path = event.get("path", "/") if isinstance(event, dict) else "/"
        query = event.get("queryParameters") or {} if isinstance(event, dict) else {}
        
        print(f"Request: {http_method} {path}")
        
        # 处理 OPTIONS 预检请求
        if http_method == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": cors_headers,
                "body": json.dumps({"message": "CORS OK"})
            }
        
        # 健康检查
        if path == "/" or path == "/health":
            return {
                "statusCode": 200,
                "headers": cors_headers,
                "body": json.dumps({
                    "status": "ok",
                    "service": "智信贷配 API",
                    "version": "2.0.0",
                    "timestamp": "2024"
                })
            }
        
        # 产品列表
        if path == "/products":
            products = load_products_simple()
            return {
                "statusCode": 200,
                "headers": cors_headers,
                "body": json.dumps(products, ensure_ascii=False)
            }
        
        # 数据库统计
        if path == "/products/stats":
            products = load_products_simple()
            return {
                "statusCode": 200,
                "headers": cors_headers,
                "body": json.dumps({
                    "total_products": len(products),
                    "status": "ok"
                }, ensure_ascii=False)
            }
        
        # 默认响应
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps({
                "path": path,
                "method": http_method,
                "message": "智信贷配 API 运行中",
                "endpoints": ["/health", "/products", "/products/stats"]
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"Error: {error_msg}")
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({
                "error": str(e),
                "type": type(e).__name__
            }, ensure_ascii=False)
        }

# 本地测试
if __name__ == "__main__":
    # 模拟测试
    test_event = {"httpMethod": "GET", "path": "/health", "queryParameters": {}}
    result = handler(test_event, None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
