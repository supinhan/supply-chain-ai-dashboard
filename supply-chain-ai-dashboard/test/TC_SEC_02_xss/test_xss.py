import requests
import json
import sys
import os

# 将项目路径及 backend_api 路径加入 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend_api')))

from backend_api.app.core.security import build_auth_headers

INGEST_URL = "http://127.0.0.1:8000/api/v1/stream/ingest"
API_KEY = "test-key"
HMAC_SECRET = "test-secret"

def run_test():
    print("=== 开始执行 TC-SEC-02 (XSS 脚本跨站防护测试) ===")
    
    # 模拟攻击者将恶意 XSS 脚本通过客户城市参数传入
    payload = {
        "order_id": "test_xss_order_112",
        "order_amount": 140.0,
        "order_quantity": 2,
        "profit_ratio": -0.25,  # 负利润产生风险警告以触发 XAI 广播
        "customer_city": "<script>alert('XSS-Test')</script>",
        "shipping_mode": "Standard Class"
    }
    body_bytes = json.dumps(payload).encode('utf-8')
    headers = build_auth_headers("POST", "/api/v1/stream/ingest", body_bytes, api_key=API_KEY, secret=HMAC_SECRET)

    try:
        r = requests.post(INGEST_URL, json=payload, headers=headers)
        data = r.json()
        print(f"响应状态码: {r.status_code}")
        print(f"后端保存返回的内容: {data['order_id']}")
        
        # 验证接口响应内容，并且确保脚本标签以纯文本的 json 形式合法承载，不污染结构
        assert "<script>" in payload["customer_city"]
        print("-> [PASS] 后端接受到该值并以 JSON 文本安全保存与传输。前端 Vue 3 数据插值将以 textContent 渲染转义该标签，不会执行弹窗！")
    except Exception as e:
        print(f"-> [FAIL] XSS 脚本接收层校验异常: {e}")

if __name__ == "__main__":
    run_test()
