import requests
import json
import sys
import os
import time

# 将项目路径及 backend_api 路径加入 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend_api')))

from backend_api.app.core.security import build_auth_headers

INGEST_URL = "http://127.0.0.1:8000/api/v1/stream/ingest"
API_KEY = "test-key"
HMAC_SECRET = "test-secret"

def run_test():
    print("=== 开始执行 TC-SEC-04 (防重放攻击与过期机制测试) ===")
    
    # 模拟在时间截口外进行重放攻击
    payload = {
        "order_id": "test_replay_order_777",
        "order_amount": 220.0,
        "order_quantity": 2,
        "profit_ratio": 0.12,
        "shipping_mode": "Standard Class"
    }
    body_bytes = json.dumps(payload).encode('utf-8')
    
    # 1. 模拟抓包并在一小时后（这里设为 3600 秒前）重放
    print("[步骤 1] 携带 1 小时前的历史合法签名进行重放请求...")
    one_hour_ago = time.time() - 3600
    replay_headers = build_auth_headers(
        "POST", "/api/v1/stream/ingest", body_bytes, 
        api_key=API_KEY, secret=HMAC_SECRET, timestamp=one_hour_ago
    )
    
    try:
        r = requests.post(INGEST_URL, json=payload, headers=replay_headers)
        print(f"响应状态码: {r.status_code}, 内容: {r.text}")
        assert r.status_code == 401
        assert "Expired request signature" in r.text
        print("-> [PASS] 重放请求由于时间窗过期被成功拦截拒签！")
    except Exception as e:
        print(f"-> [FAIL] 重放攻击防御测试异常: {e}")

if __name__ == "__main__":
    run_test()
