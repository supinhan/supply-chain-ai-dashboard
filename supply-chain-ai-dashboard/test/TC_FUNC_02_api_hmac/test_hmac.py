import sys
import os
import requests
import json
import time

# 将项目路径及 backend_api 路径加入 sys.path 以便导入 security 模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend_api')))

from backend_api.app.core.security import build_auth_headers

URL = "http://127.0.0.1:8000/api/v1/stream/ingest"
API_KEY = "test-key"
HMAC_SECRET = "test-secret"

payload = {
    "order_id": "test_order_hmac_001",
    "order_amount": 120.5,
    "order_quantity": 2,
    "profit_ratio": 0.25,
    "shipping_mode": "Standard Class"
}
body_bytes = json.dumps(payload).encode('utf-8')

def run_test():
    print("=== 开始执行 TC-FUNC-02 (API 安全签名与篡改校验测试) ===")
    
    # 1. 测试未携带任何签名的请求
    print("\n[步骤 1] 发送未带签名的请求...")
    try:
        r = requests.post(URL, json=payload)
        print(f"响应状态码: {r.status_code}, 返回内容: {r.text}")
        assert r.status_code == 401
        print("-> [PASS] 无签名请求成功被拦截！")
    except Exception as e:
        print(f"-> [FAIL] 步骤 1 异常: {e}")

    # 2. 测试修改内容但未更新签名的请求（篡改测试）
    print("\n[步骤 2] 发送修改内容但未更新签名的请求 (篡改数据)...")
    headers = build_auth_headers("POST", "/api/v1/stream/ingest", body_bytes, api_key=API_KEY, secret=HMAC_SECRET)
    # 修改 body，但保留旧签名
    tampered_payload = payload.copy()
    tampered_payload["order_amount"] = 9999.0
    try:
        r = requests.post(URL, json=tampered_payload, headers=headers)
        print(f"响应状态码: {r.status_code}, 返回内容: {r.text}")
        assert r.status_code == 401
        print("-> [PASS] 数据篡改请求成功被拦截！")
    except Exception as e:
        print(f"-> [FAIL] 步骤 2 异常: {e}")

    # 3. 测试过期签名的请求
    print("\n[步骤 3] 发送过期签名的请求 (10分钟前的时间戳)...")
    ten_mins_ago = time.time() - 600
    expired_headers = build_auth_headers(
        "POST", "/api/v1/stream/ingest", body_bytes, 
        api_key=API_KEY, secret=HMAC_SECRET, timestamp=ten_mins_ago
    )
    try:
        r = requests.post(URL, json=payload, headers=expired_headers)
        print(f"响应状态码: {r.status_code}, 返回内容: {r.text}")
        assert r.status_code == 401
        print("-> [PASS] 过期请求成功被拦截！")
    except Exception as e:
        print(f"-> [FAIL] 步骤 3 异常: {e}")

    # 4. 测试合法且正确签名的请求
    print("\n[步骤 4] 发送合法且正确签名的请求...")
    valid_headers = build_auth_headers("POST", "/api/v1/stream/ingest", body_bytes, api_key=API_KEY, secret=HMAC_SECRET)
    try:
        r = requests.post(URL, json=payload, headers=valid_headers)
        print(f"响应状态码: {r.status_code}, 返回内容: {r.text}")
        assert r.status_code == 200
        print("-> [PASS] 合法签名请求成功注入！")
    except Exception as e:
        print(f"-> [FAIL] 步骤 4 异常: {e}")

if __name__ == "__main__":
    run_test()
