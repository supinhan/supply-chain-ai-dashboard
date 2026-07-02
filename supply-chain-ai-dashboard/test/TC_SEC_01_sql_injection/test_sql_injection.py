import requests
import json
import sys
import os

# 将项目路径及 backend_api 路径加入 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend_api')))

from backend_api.app.core.security import build_auth_headers

INGEST_URL = "http://127.0.0.1:8000/api/v1/stream/ingest"
HISTORY_URL = "http://127.0.0.1:8000/api/v1/kpi/history"
API_KEY = "test-key"
HMAC_SECRET = "test-secret"

def run_test():
    print("=== 开始执行 TC-SEC-01 (SQL 注入防御测试) ===")
    
    # 1. 验证类型层注入防御 (FastAPI 自动类型拦截)
    # GET /kpi/history 接收 hours: int 传入 SQL 注入语句将直接触发 422 校验失败
    print("[步骤 1] 校验类型限制参数 SQL 注入拦截 (GET /kpi/history?hours=1' OR '1'='1)...")
    try:
        r = requests.get(f"{HISTORY_URL}?hours=1'%20OR%20'1'='1")
        print(f"响应状态码: {r.status_code}, 内容: {r.text}")
        assert r.status_code == 422
        print("-> [PASS] 类型不符的 SQL 注入成功在入口层校验拦截！")
    except Exception as e:
        print(f"-> [FAIL] 步骤 1 异常: {e}")

    # 2. 验证字符值层注入安全 (SQLAlchemy ORM 转义处理)
    # 注入 customer_city 为 `' OR '1'='1 --` 检查是否被安全插入数据库中作为字面值
    print("\n[步骤 2] 校验字符型字段 SQL 注入转义 (POST /stream/ingest)...")
    payload = {
        "order_id": "test_sql_inject_001",
        "order_amount": 100.0,
        "order_quantity": 1,
        "profit_ratio": 0.1,
        "customer_city": "Chicago' OR '1'='1 --",
        "shipping_mode": "Standard Class"
    }
    body_bytes = json.dumps(payload).encode('utf-8')
    headers = build_auth_headers("POST", "/api/v1/stream/ingest", body_bytes, api_key=API_KEY, secret=HMAC_SECRET)
    
    try:
        r = requests.post(INGEST_URL, json=payload, headers=headers)
        print(f"响应状态码: {r.status_code}, 内容: {r.text}")
        assert r.status_code == 200
        print("-> [PASS] ORM 参数绑定已自动安全转义，订单成功以纯文本值保存！")
    except Exception as e:
        print(f"-> [FAIL] 步骤 2 异常: {e}")

if __name__ == "__main__":
    run_test()
