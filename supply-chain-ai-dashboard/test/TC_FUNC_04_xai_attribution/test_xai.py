import sys
import os
import requests
import json

# 将项目路径及 backend_api 路径加入 sys.path 以便导入 security 模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend_api')))

from backend_api.app.core.security import build_auth_headers

URL = "http://127.0.0.1:8000/api/v1/stream/ingest"
API_KEY = "test-key"
HMAC_SECRET = "test-secret"

def run_test():
    print("=== 开始执行 TC-FUNC-04 (XAI 局部特征归因归一化测试) ===")
    
    payload = {
        "order_id": "test_order_xai_888",
        "order_amount": 500.0,
        "order_quantity": 5,
        "profit_ratio": -0.3,  # 负利润触发硬拦截与 XAI 随机微扰归因
        "shipping_mode": "Same Day"
    }
    body_bytes = json.dumps(payload).encode('utf-8')
    headers = build_auth_headers("POST", "/api/v1/stream/ingest", body_bytes, api_key=API_KEY, secret=HMAC_SECRET)

    try:
        r = requests.post(URL, json=payload, headers=headers)
        data = r.json()
        print(f"响应状态码: {r.status_code}")
        
        alert = data.get("alert")
        assert alert is not None
        xai_analysis = alert.get("xai_analysis", {})
        print(f"提取的 XAI 归因字典: {xai_analysis}")

        # 1. 验证归因特征项是否存在
        assert "订单利润" in xai_analysis
        assert "订单总额" in xai_analysis
        assert "运输模式" in xai_analysis
        
        # 2. 验证权重之和是否归一化（由于浮点数精度，之和应非常接近 1.0）
        total_weight = sum(xai_analysis.values())
        print(f"XAI 权重总和: {total_weight}")
        assert abs(total_weight - 1.0) < 0.01
        
        # 3. 验证对于负利润订单，“订单利润”特征占主导地位
        assert xai_analysis["订单利润"] > xai_analysis["订单总额"]
        assert xai_analysis["订单利润"] > xai_analysis["运输模式"]
        
        print("-> [PASS] XAI 可解释性分析模型输出的特征归因格式及数学归一化校验全部通过！")
    except Exception as e:
        print(f"-> [FAIL] XAI 校验异常: {e}")

if __name__ == "__main__":
    run_test()
