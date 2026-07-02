import concurrent.futures
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
    "order_id": "perf_load_order_",
    "order_amount": 95.0,
    "order_quantity": 2,
    "profit_ratio": 0.08,
    "shipping_mode": "Standard Class"
}

def single_ingest(i):
    iter_payload = payload.copy()
    iter_payload["order_id"] = f"perf_load_order_{int(time.time() * 1000)}_{i}"
    body_bytes = json.dumps(iter_payload).encode('utf-8')
    headers = build_auth_headers("POST", "/api/v1/stream/ingest", body_bytes, api_key=API_KEY, secret=HMAC_SECRET)
    try:
        r = requests.post(INGEST_URL, json=iter_payload, headers=headers, timeout=5)
        return r.status_code
    except Exception as e:
        return str(e)

def single_forecast(i):
    try:
        r = requests.get(FORECAST_URL, timeout=5)
        return r.status_code
    except Exception as e:
        return str(e)

def run_test():
    print("=== 开始执行 TC-PERF-02 (高吞吐并发压力测试) ===")
    
    # 使用 ThreadPoolExecutor 模拟多线程并发
    workers = 8
    total_calls = 40
    print(f"模拟并发线程数: {workers}, 总调用请求: {total_calls} 次...")
    
    success_count = 0
    t0 = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        # 发送一半 Ingest，一半 Forecast
        futures = []
        for i in range(total_calls // 2):
            futures.append(executor.submit(single_ingest, i))
            futures.append(executor.submit(single_forecast, i))
            
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res == 200:
                success_count += 1
                
    t1 = time.time()
    elapsed = t1 - t0
    success_rate = (success_count / total_calls) * 100
    qps = total_calls / elapsed
    
    print("\n--- 并发测试结果 ---")
    print(f"总耗时: {elapsed:.2f} s")
    print(f"成功次数: {success_count} / {total_calls}")
    print(f"请求成功率: {success_rate:.1f}%")
    print(f"吞吐量 (QPS): {qps:.1f} req/sec")
    
    assert success_rate > 90, f"并发请求成功率低于 90% ({success_rate}%)"
    print("-> [PASS] 高并发压力测试通过，多线程下系统仍能稳定处理请求！")

if __name__ == "__main__":
    run_test()
