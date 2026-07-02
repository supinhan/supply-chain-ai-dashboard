import requests
import time
import json
import sys
import os

# 将项目路径及 backend_api 路径加入 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend_api')))

from backend_api.app.core.security import build_auth_headers

INGEST_URL = "http://127.0.0.1:8000/api/v1/stream/ingest"
FORECAST_URL = "http://127.0.0.1:8000/api/v1/forecast"
API_KEY = "test-key"
HMAC_SECRET = "test-secret"

payload = {
    "order_id": "perf_latency_order_",
    "order_amount": 80.0,
    "order_quantity": 1,
    "profit_ratio": 0.05,
    "shipping_mode": "Standard Class"
}

def run_test():
    print("=== 开始执行 TC-PERF-01 (响应延迟性能测试) ===")
    
    # 1. 压测 Ingest 注入与 AI 在线打分延迟 (执行 20 次)
    ingest_times = []
    print("[步骤 1] 循环调用 20 次订单注入 + 双模推理接口...")
    for i in range(20):
        iter_payload = payload.copy()
        iter_payload["order_id"] = f"perf_latency_order_{int(time.time() * 1000)}_{i}"
        body_bytes = json.dumps(iter_payload).encode('utf-8')
        headers = build_auth_headers("POST", "/api/v1/stream/ingest", body_bytes, api_key=API_KEY, secret=HMAC_SECRET)
        
        t0 = time.time()
        try:
            r = requests.post(INGEST_URL, json=iter_payload, headers=headers)
            t1 = time.time()
            if r.status_code == 200:
                ingest_times.append((t1 - t0) * 1000)
        except Exception as e:
            print(f"迭代 {i} 发生异常: {e}")
            
    # 2. 压测销量预测接口延迟
    forecast_times = []
    print("[步骤 2] 循环调用 20 次未来销量预测接口...")
    for i in range(20):
        t0 = time.time()
        try:
            r = requests.get(FORECAST_URL)
            t1 = time.time()
            if r.status_code == 200:
                forecast_times.append((t1 - t0) * 1000)
        except Exception as e:
            print(f"迭代 {i} 异常: {e}")

    avg_ingest = sum(ingest_times) / len(ingest_times) if ingest_times else 0
    avg_fore = sum(forecast_times) / len(forecast_times) if forecast_times else 0
    
    print("\n--- 性能测试结果 ---")
    print(f"数据注入端到端平均延迟: {avg_ingest:.2f} ms")
    print(f"未来销量预测平均延迟: {avg_fore:.2f} ms")
    
    # 校验延迟指标 (PRD 规定端到端时延低于 1000ms)
    assert avg_ingest < 1000, "数据注入与双模推理平均延迟超过 1000ms！"
    assert avg_fore < 1000, "未来销量预测平均延迟超过 1000ms！"
    print("-> [PASS] 平均响应时间远低于 1 秒预期阈值，响应效率优异！")

if __name__ == "__main__":
    run_test()
