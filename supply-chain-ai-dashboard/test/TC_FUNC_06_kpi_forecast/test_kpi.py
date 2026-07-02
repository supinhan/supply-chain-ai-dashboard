import requests
import json

HIST_URL = "http://127.0.0.1:8000/api/v1/kpi/history?hours=24"
FORE_URL = "http://127.0.0.1:8000/api/v1/forecast"

def run_test():
    print("=== 开始执行 TC-FUNC-06 (历史趋势与销量预测查询测试) ===")
    
    # 1. 测试历史趋势接口
    print("\n[步骤 1] 调取历史24小时 KPI 聚合趋势接口...")
    try:
        r = requests.get(HIST_URL)
        print(f"历史趋势状态码: {r.status_code}")
        data = r.json()
        assert "items" in data
        items = data["items"]
        print(f"返回条数: {len(items)}")
        if items:
            print(f"首项结构: {items[0]}")
            assert "bucket" in items[0]
            assert "order_count" in items[0]
        print("-> [PASS] 历史 KPI 聚合接口校验成功！")
    except Exception as e:
        print(f"-> [FAIL] 步骤 1 异常: {e}")

    # 2. 测试销量预测接口
    print("\n[步骤 2] 调取未来7天时序销量预测接口...")
    try:
        r = requests.get(FORE_URL)
        print(f"销量预测状态码: {r.status_code}")
        data = r.json()
        assert "days" in data
        assert "values" in data
        print(f"预测天数序列 (days): {data['days']}")
        print(f"对应销量值序列 (values): {data['values']}")
        assert len(data["days"]) == len(data["values"])
        print("-> [PASS] 未来7天时序销量预测接口校验成功！")
    except Exception as e:
        print(f"-> [FAIL] 步骤 2 异常: {e}")

if __name__ == "__main__":
    run_test()
