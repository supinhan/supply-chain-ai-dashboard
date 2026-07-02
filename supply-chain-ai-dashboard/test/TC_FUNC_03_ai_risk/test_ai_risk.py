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

def run_test():
    print("=== 开始执行 TC-FUNC-03 (双模 AI 预警机制与 XAI 可解释归因测试) ===")

    # 1. 发送倒贴亏损订单 (触发财务规则硬拦截)
    print("\n[测试用例 1] 注入负利润亏损订单 (触发规则硬拦截)...")
    loss_payload = {
        "order_id": "test_order_loss_999",
        "order_amount": 300.0,
        "order_quantity": 3,
        "profit_ratio": -0.2,  # 负利润
        "shipping_mode": "First Class",
        "customer_city": "Chicago",
        "product_category": "Sporting Goods"
    }
    body_bytes = json.dumps(loss_payload).encode('utf-8')
    headers = build_auth_headers("POST", "/api/v1/stream/ingest", body_bytes, api_key=API_KEY, secret=HMAC_SECRET)
    
    try:
        r = requests.post(URL, json=loss_payload, headers=headers)
        print(f"响应状态码: {r.status_code}")
        data = r.json()
        print(f"返回结果: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        # 验证是否拦截
        assert data["is_high_risk"] is True
        assert 0.90 <= data["risk_score"] <= 0.985
        assert data["alert"] is not None
        assert "订单利润" in data["alert"]["xai_analysis"]
        print("-> [PASS] 负利润硬拦截规则测试成功！XAI 归因包含 订单利润 权重。")
    except Exception as e:
        print(f"-> [FAIL] 用例 1 异常: {e}")

    # 2. 发送普通正常盈利订单 (进入 ML 模型并行评分)
    print("\n[测试用例 2] 注入正常盈利订单 (进入机器学习打分)...")
    normal_payload = {
        "order_id": "test_order_normal_001",
        "order_amount": 150.0,
        "order_quantity": 1,
        "profit_ratio": 0.12,  # 正利润
        "shipping_mode": "Standard Class",
        "customer_city": "New York",
        "product_category": "Electronics"
    }
    body_bytes = json.dumps(normal_payload).encode('utf-8')
    headers = build_auth_headers("POST", "/api/v1/stream/ingest", body_bytes, api_key=API_KEY, secret=HMAC_SECRET)
    
    try:
        r = requests.post(URL, json=normal_payload, headers=headers)
        print(f"响应状态码: {r.status_code}")
        data = r.json()
        print(f"返回结果: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        # 验证机器学习输出
        assert "risk_score" in data
        print("-> [PASS] 普通正常盈利订单推理测试成功！模型返回了风险分值。")
    except Exception as e:
        print(f"-> [FAIL] 用例 2 异常: {e}")

if __name__ == "__main__":
    run_test()
