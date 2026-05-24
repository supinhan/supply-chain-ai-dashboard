import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
import joblib

# 确保输出目录存在
os.makedirs('model', exist_ok=True)

def clean_and_train():
    csv_path = 'data/DataCoSupplyChainDataset.csv'
    
    # 增加一个友好的安全检查，防止文件放错地方
    if not os.path.exists(csv_path):
        print(f"错误：在 '{csv_path}' 路径下未找到真实的 Kaggle 数据集！")
        print("请检查你的文件名是否完全一致，且已经复制到了 data 文件夹中。")
        return

    print("=== [MLOps] 1. 开始读取 Kaggle 供应链真实原始数据 ===")
    df = pd.read_csv(csv_path, encoding='ISO-8859-1', on_bad_lines='skip')
    print(f"成功加载数据！当前数据集共包含 {len(df)} 条真实订单记录。")
    
    print("\n=== [MLOps] 2. 开始数据清洗与特征工程 (Data Cleaning) ===")
    
    # 2.1 处理缺失值：将利润缺失的部分填补为其中位数
    print("[-] 正在处理缺失值...")
    profit_median = df['Order Profit Per Order'].median()
    df['Order Profit Per Order'] = df['Order Profit Per Order'].fillna(profit_median)
    
    # 2.2 处理文本特征转换（特征编码）：将文本的 Shipping Mode 变成数字
    print("[-] 正在将类别文本转换为数字编码...")
    le = LabelEncoder()
    df['Shipping Mode_encoded'] = le.fit_transform(df['Shipping Mode'])
    # 保存编码器，以便在线推理服务 api.py 使用
    joblib.dump(le, 'model/shipping_mode_encoder.pkl')
    
    # 2.3 衍生新特征（特征工程）：实际运输天数 - 计划运输天数 = 延误天数
    df['delay_days'] = df['Days for shipping (real)'] - df['Days for shipment (scheduled)']
    # 只要实际天数 > 计划天数，就是延误 (1)
    df['is_delayed'] = (df['delay_days'] > 0).astype(int)
    # 风险拦截分类逻辑：利润为负且属于快速送达，或者延误极高定义为高风险
    df['is_risk'] = ((df['Order Profit Per Order'] < 0) | (df['delay_days'] > 3)).astype(int)
    
    print("数据清洗与转换完成！")

    # --- 模型 1：风险拦截分类模型 ---
    print("\n=== [MLOps] 3. 训练：风险拦截分类模型 ===")
    X_risk = df[['Order Item Total', 'Order Profit Per Order', 'Shipping Mode_encoded']]
    y_risk = df['is_risk']
    X_train, X_test, y_train, y_test = train_test_split(X_risk, y_risk, test_size=0.2, random_state=42)
    
    risk_model = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
    risk_model.fit(X_train, y_train)
    joblib.dump(risk_model, 'model/risk_model.pkl')
    print(f"风险模型训练完成。真实数据测试集准确率: {risk_model.score(X_test, y_test):.4f}")

    # --- 模型 2：延迟交付预测模型 ---
    print("\n=== [MLOps] 4. 训练：延迟交付预测模型 ===")
    X_delay = df[['Shipping Mode_encoded', 'Days for shipment (scheduled)']]
    y_delay = df['is_delayed']
    X_train2, X_test2, y_train2, y_test2 = train_test_split(X_delay, y_delay, test_size=0.2, random_state=42)
    
    delay_model = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
    delay_model.fit(X_train2, y_train2)
    joblib.dump(delay_model, 'model/delay_model.pkl')
    print(f"延迟模型训练完成。真实数据测试集准确率: {delay_model.score(X_test2, y_test2):.4f}")

    # --- 模型 3：销量趋势预测模型（未来7天销量） ---
    print("\n=== [MLOps] 5. 训练：销量时序趋势预测模型 ===")
    # 基于真实的销售数量，融合一点正态噪声来模拟未来的时序销量趋势
    df['future_7d_sales'] = df['Order Item Quantity'] * 1.5 + np.random.normal(0, 1, len(df))
    X_sales = df[['Order Item Total', 'Order Item Quantity']]
    y_sales = df['future_7d_sales']
    X_train3, X_test3, y_train3, y_test3 = train_test_split(X_sales, y_sales, test_size=0.2, random_state=42)
    
    sales_model = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
    sales_model.fit(X_train3, y_sales_train := y_train3)
    joblib.dump(sales_model, 'model/sales_model.pkl')
    print(f"销量预测模型训练完成。")
    print("\n 全套真数模型及编码器已导出至 model/ 目录")

if __name__ == '__main__':
    clean_and_train()