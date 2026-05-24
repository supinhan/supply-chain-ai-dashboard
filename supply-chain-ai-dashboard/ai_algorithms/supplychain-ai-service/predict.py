import joblib
import pandas as pd

def test_local_prediction():
    print("=== 本地离线模型测试 ===")
    
    # 加载风险模型
    try:
        model = joblib.load('model/risk_model.pkl')
        print("[-] 成功加载 model/risk_model.pkl")
    except Exception as e:
        print(f"[!] 模型加载失败，请先运行 train_model.py。错误: {e}")
        return

    # 构造测试特征（需要与训练时的特征顺序和名称完全一致）
    # 特征: ['order_amount', 'profit_ratio', 'shipping_delay']
    test_data = pd.DataFrame([{
        "order_amount": 1200,
        "profit_ratio": -0.1,    # 负利润，增加风险概率
        "shipping_delay": 8      # 高延迟，增加风险概率
    }])
    
    # 获取概率 (predict_proba 返回 [类别0的概率, 类别1的概率])
    probabilities = model.predict_proba(test_data)
    risk_score = probabilities[0][1] # 取类别1（有风险）的概率
    
    print(f"[-] 输入特征: \n{test_data.to_dict(orient='records')[0]}")
    print(f"[-] 预测风险得分 (Risk Score): {risk_score:.4f}")
    
    if risk_score > 0.85:
        print("[!] 警告：高风险订单！")
    else:
        print("[-] 订单风险在可控范围内。")

if __name__ == "__main__":
    test_local_prediction()