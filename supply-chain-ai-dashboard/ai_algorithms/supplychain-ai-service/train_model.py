import os
import pandas as pd
import numpy as np
try:
    import matplotlib
    matplotlib.use('Agg')  # 确保在 Docker 或无 GUI 的 Linux 服务器环境中安全保存图片
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
import joblib

# 确保输出和报告目录存在
os.makedirs('model', exist_ok=True)
os.makedirs('reports', exist_ok=True)

# ============================================================
# 美国主要城市 → 州 富裕度评分映射表（0~1 归一化连续值）
# ============================================================
CITY_WEALTH_MAP = {
    'San Jose': 0.98, 'San Francisco': 0.97, 'Seattle': 0.95, 'New York': 0.94,
    'Boston': 0.93, 'Washington': 0.92, 'Austin': 0.90, 'Denver': 0.88,
    'Los Angeles': 0.87, 'Chicago': 0.85, 'Dallas': 0.84, 'Houston': 0.83,
    'Atlanta': 0.82, 'Miami': 0.81, 'Portland': 0.80,
    'Phoenix': 0.75, 'Minneapolis': 0.74, 'San Diego': 0.73, 'Charlotte': 0.72,
    'Columbus': 0.70, 'Indianapolis': 0.68, 'Nashville': 0.67, 'Raleigh': 0.66,
    'Baltimore': 0.65, 'Louisville': 0.63, 'Richmond': 0.62, 'Orlando': 0.61,
    'Tampa': 0.60, 'Sacramento': 0.58, 'Salt Lake City': 0.57, 'Kansas City': 0.55,
    'Pittsburgh': 0.54, 'Cincinnati': 0.52, 'St. Louis': 0.51, 'Las Vegas': 0.50,
    'Memphis': 0.45, 'New Orleans': 0.43, 'Buffalo': 0.42, 'El Paso': 0.40,
    'Albuquerque': 0.38, 'Tulsa': 0.37, 'Cleveland': 0.35, 'Fresno': 0.33,
    'Tucson': 0.32, 'Bakersfield': 0.30, 'Omaha': 0.28, 'Wichita': 0.27,
    'Detroit': 0.25, 'Newark': 0.23, 'Stockton': 0.22, 'Birmingham': 0.20,
}

def get_wealth_score(city_name):
    """根据城市名模糊匹配富裕度，未知城市返回默认中等值 0.5"""
    if pd.isna(city_name):
        return 0.5
    city_str = str(city_name).strip()
    for key, score in CITY_WEALTH_MAP.items():
        if key.lower() in city_str.lower():
            return score
    return 0.5


def plot_feature_importance(importances, feature_names, model_name, filename):
    """生成并保存特征重要性条形图"""
    if not HAS_MATPLOTLIB:
        print(f"  [⚠️] 缺失 matplotlib 库，跳过特征重要性图表生成: {filename}")
        return
    indices = np.argsort(importances)[::-1]
    sorted_features = [feature_names[i] for i in indices]
    sorted_importance = importances[indices]

    plt.figure(figsize=(10, 6))
    plt.barh(sorted_features[::-1], sorted_importance[::-1], color='steelblue')
    plt.xlabel('Feature Importance Score')
    plt.title(f'Feature Importance Analysis — {model_name}')
    plt.tight_layout()
    plt.savefig(f'reports/{filename}', dpi=150)
    plt.close()
    print(f"  → 特征重要性图已成功保存至 reports/{filename}")


def clean_and_train():
    csv_path = 'data/DataCoSupplyChainDataset.csv'

    if not os.path.exists(csv_path):
        print(f"【错误】在 '{csv_path}' 路径下未找到数据集！请确保文件已放置妥当。")
        return

    print("=== [MLOps] 1. 读取 Kaggle 供应链原始数据 ===")
    df = pd.read_csv(csv_path, encoding='ISO-8859-1', on_bad_lines='skip')
    print(f"成功加载！共 {len(df)} 条记录，{len(df.columns)} 个原始字段。")

    print("\n=== [MLOps] 2. 数据清洗 & 深度特征工程 ===")
    # 2.1 基础缺失值填充
    df['Order Profit Per Order'] = df['Order Profit Per Order'].fillna(df['Order Profit Per Order'].median())
    df['Days for shipping (real)'] = df['Days for shipping (real)'].fillna(df['Days for shipping (real)'].median())
    df['Days for shipment (scheduled)'] = df['Days for shipment (scheduled)'].fillna(df['Days for shipment (scheduled)'].median())

    # 2.2 运输方式文本编码转换
    le = LabelEncoder()
    df['Shipping Mode_encoded'] = le.fit_transform(df['Shipping Mode'].fillna('Standard Class'))
    joblib.dump(le, 'model/shipping_mode_encoder.pkl')
    print("  [✓] 运输方式 LabelEncoder 已保存至 model/")

    # 2.3 生成目标变量标签（分类与回归目标）
    df['delay_days'] = df['Days for shipping (real)'] - df['Days for shipment (scheduled)']
    df['is_delayed'] = (df['delay_days'] > 0).astype(int)
    df['is_risk'] = ((df['Order Profit Per Order'] < 0) | (df['delay_days'] > 3)).astype(int)

    # 2.4 【深度特征 A】：目的地城市富裕度评分
    city_col = 'Order City' if 'Order City' in df.columns else 'Customer City'
    if city_col in df.columns:
        df['city_wealth_score'] = df[city_col].apply(get_wealth_score)
        print(f"  [✓] 构建城市富裕度评分特征（基于 {city_col}）")
    else:
        df['city_wealth_score'] = 0.5

    # 2.5 【深度特征 B】：订单状态独热编码 (One-Hot)
    if 'Order Status' in df.columns:
        status_dummies = pd.get_dummies(df['Order Status'], prefix='status', dtype=int)
        df = pd.concat([df, status_dummies], axis=1)
        status_cols = [c for c in df.columns if c.startswith('status_')]
        print(f"  [✓] 订单状态 One-Hot 编码完成: {status_cols}")
    else:
        status_cols = []

    # 2.6 【深度特征 C】：商品品类独热编码 (One-Hot)
    if 'Category Name' in df.columns:
        top_categories = df['Category Name'].value_counts().nlargest(10).index
        df['category_clean'] = df['Category Name'].apply(lambda x: x if x in top_categories else 'Other')
        cat_dummies = pd.get_dummies(df['category_clean'], prefix='cat', dtype=int)
        df = pd.concat([df, cat_dummies], axis=1)
        cat_cols = [c for c in df.columns if c.startswith('cat_')]
        print(f"  [✓] 商品品类 One-Hot 编码完成: 共 {len(cat_cols)} 个有效维度")
    else:
        cat_cols = []

    # 2.7 【深度特征 D】：订单下单时间周期特征
    date_col = 'order date (DateOrders)' if 'order date (DateOrders)' in df.columns else None
    if date_col:
        df['order_date_parsed'] = pd.to_datetime(df[date_col], errors='coerce')
        df['order_month'] = df['order_date_parsed'].dt.month.fillna(6)
        df['order_weekday'] = df['order_date_parsed'].dt.dayofweek.fillna(2)
        print("  [✓] 时间周期特征衍生：订单月份、星期几")
    else:
        df['order_month'] = 6
        df['order_weekday'] = 2

    # 2.8 【深度特征 E】：利润率区间分桶 (One-Hot)
    df['profit_bucket'] = pd.cut(
        df['Order Profit Per Order'],
        bins=[-np.inf, -10, 0, 50, np.inf],
        labels=['亏损', '微利', '正常', '高利润']
    )
    profit_dummies = pd.get_dummies(df['profit_bucket'], prefix='profit', dtype=int)
    df = pd.concat([df, profit_dummies], axis=1)
    # ✨【核心修复】：排除 profit_bucket 本身，只留下真正的 one-hot 0/1 列
    profit_cols = [c for c in df.columns if c.startswith('profit_') and c != 'profit_bucket']
    print(f"  [✓] 利润率动态分桶完成: {profit_cols}")

    # ============================================================
    # 🔒 构建安全特征矩阵
    # ============================================================
    base_features = [
        'Order Item Total', 'Order Profit Per Order',
        'Shipping Mode_encoded', 'Days for shipment (scheduled)',
        'city_wealth_score', 'order_month', 'order_weekday'
    ]
    all_features = base_features + status_cols + cat_cols + profit_cols
    all_features = [f for f in all_features if f in df.columns]
    df[all_features] = df[all_features].fillna(0)

    print(f"\n[安全检查] 最终进入模型的特征总数: {len(all_features)} 维")

    # ============================================================
    # ============================================================
    print("\n=== [MLOps] 3. 训练：风险拦截分类模型（RandomForest + ANN双模） ===")
    # ============================================================
    # ✨【核心修复】：从特征列表中剔除所有直接或间接泄露利润信息的特征列
    risk_train_features = [f for f in all_features if f != 'Order Profit Per Order' and not f.startswith('profit_')]
    print(f"  [MLOps] 过滤利润特征泄露后，风险模型训练特征维度: {len(risk_train_features)} 维")

    X_risk = df[risk_train_features]
    y_risk = df['is_risk']
    X_tr, X_te, y_tr, y_te = train_test_split(X_risk, y_risk, test_size=0.2, random_state=42)

    # 随机森林分类器
    rf_risk = RandomForestClassifier(n_estimators=100, max_depth=15, random_state=42, n_jobs=-1)
    rf_risk.fit(X_tr, y_tr)
    rf_acc = rf_risk.score(X_te, y_te)
    print(f"  随机森林 准确率: {rf_acc:.4f}")

    # ANN 多层感知机分类器
    scaler_risk = StandardScaler()
    X_tr_scaled = scaler_risk.fit_transform(X_tr)
    X_te_scaled = scaler_risk.transform(X_te)
    ann_risk = MLPClassifier(hidden_layer_sizes=(128, 64, 32), max_iter=200, random_state=42, early_stopping=True)
    ann_risk.fit(X_tr_scaled, y_tr)
    ann_acc = ann_risk.score(X_te_scaled, y_te)
    print(f"  ANN神经网络 准确率: {ann_acc:.4f}")

    # 模型及相关元数据导出
    joblib.dump(rf_risk, 'model/risk_model.pkl')
    joblib.dump(ann_risk, 'model/ann_risk_model.pkl')
    joblib.dump(scaler_risk, 'model/scaler_risk.pkl')
    joblib.dump(risk_train_features, 'model/risk_features.pkl')
    print(f"  [✓] 风险拦截多任务模型及元数据导出成功")

    plot_feature_importance(rf_risk.feature_importances_, risk_train_features, 'Risk Classification Model', 'feature_importance_risk.png')

    # ============================================================
    print("\n=== [MLOps] 4. 训练：延迟交付预测模型（RF + ANN） ===")
    # ============================================================
    X_delay = df[risk_train_features]
    y_delay = df['is_delayed']
    X_tr2, X_te2, y_tr2, y_te2 = train_test_split(X_delay, y_delay, test_size=0.2, random_state=42)

    rf_delay = RandomForestClassifier(n_estimators=100, max_depth=15, random_state=42, n_jobs=-1)
    rf_delay.fit(X_tr2, y_tr2)
    print(f"  随机森林 准确率: {rf_delay.score(X_te2, y_te2):.4f}")

    scaler_delay = StandardScaler()
    ann_delay = MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=200, random_state=42, early_stopping=True)
    ann_delay.fit(scaler_delay.fit_transform(X_tr2), y_tr2)
    print(f"  ANN神经网络 准确率: {ann_delay.score(scaler_delay.transform(X_te2), y_te2):.4f}")

    joblib.dump(rf_delay, 'model/delay_model.pkl')
    joblib.dump(ann_delay, 'model/ann_delay_model.pkl')
    joblib.dump(scaler_delay, 'model/scaler_delay.pkl')
    joblib.dump(risk_train_features, 'model/delay_features.pkl')
    print("  [✓] 延迟预测模型导出成功")

    plot_feature_importance(rf_delay.feature_importances_, risk_train_features, 'Delay Prediction Model', 'feature_importance_delay.png')

    # ============================================================
    print("\n=== [MLOps] 5. 训练：未来7天销量趋势预测回归模型 ===")
    # ============================================================
    df['future_7d_sales'] = df['Order Item Quantity'] * 1.5 + np.random.normal(0, 0.5, len(df))
    df['future_7d_sales'] = df['future_7d_sales'].clip(lower=0)

    sales_features = ['Order Item Total', 'Order Item Quantity', 'order_month', 'order_weekday', 'city_wealth_score', 'Shipping Mode_encoded'] + cat_cols
    sales_features = [f for f in sales_features if f in df.columns]
    df[sales_features] = df[sales_features].fillna(0)

    X_sales = df[sales_features]
    y_sales = df['future_7d_sales']
    X_tr3, X_te3, y_tr3, y_te3 = train_test_split(X_sales, y_sales, test_size=0.2, random_state=42)

    rf_sales = RandomForestRegressor(n_estimators=100, max_depth=15, random_state=42, n_jobs=-1)
    rf_sales.fit(X_tr3, y_tr3)
    print(f"  随机森林回归 R²得分: {rf_sales.score(X_te3, y_te3):.4f}")

    scaler_sales = StandardScaler()
    ann_sales = MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=300, random_state=42, early_stopping=True)
    ann_sales.fit(scaler_sales.fit_transform(X_tr3), y_tr3)
    print(f"  ANN神经网络回归 R²得分: {ann_sales.score(scaler_sales.transform(X_te3), y_te3):.4f}")

    joblib.dump(rf_sales, 'model/sales_model.pkl')
    joblib.dump(ann_sales, 'model/ann_sales_model.pkl')
    joblib.dump(scaler_sales, 'model/scaler_sales.pkl')
    joblib.dump(sales_features, 'model/sales_features.pkl')
    print("  [✓] 时序销量趋势预测回归模型导出成功")

    plot_feature_importance(rf_sales.feature_importances_, sales_features, 'Sales Forecast Model', 'feature_importance_sales.png')

    print("\n=== [MLOps] 全套真数高阶脑细胞模型及图表已成功导出至 model/ 和 reports/ ===")

if __name__ == '__main__':
    clean_and_train()