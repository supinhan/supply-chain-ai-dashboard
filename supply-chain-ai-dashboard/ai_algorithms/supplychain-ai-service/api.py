from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel
from typing import Optional, List, Dict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import hashlib
import hmac
import joblib
import pandas as pd
import numpy as np
import os
import time

ml_models = {}

API_KEY_HEADER = "X-SCAI-API-Key"
TIMESTAMP_HEADER = "X-SCAI-Timestamp"
SIGNATURE_HEADER = "X-SCAI-Signature"
SIGNATURE_VERSION = "v1"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """容器启动时一次性预加载所有 pkl 模型文件，避免并发请求时重复读取磁盘"""
    print("[LifeSpan] 正在加载供应链核心 AI 脑细胞集群...")
    
    ml_models["risk"] = joblib.load('model/risk_model.pkl')
    ml_models["encoder"] = joblib.load('model/shipping_mode_encoder.pkl')
    ml_models["sales"] = joblib.load('model/sales_model.pkl')
    
    if os.path.exists('model/risk_features.pkl'):
        ml_models["risk_features"] = joblib.load('model/risk_features.pkl')
    if os.path.exists('model/sales_features.pkl'):
        ml_models["sales_features"] = joblib.load('model/sales_features.pkl')
    if os.path.exists('model/delay_model.pkl'):
        ml_models["delay"] = joblib.load('model/delay_model.pkl')

    print(f"[LifeSpan] 加载完成！已就绪特征维度数: {len(ml_models.get('risk_features', []))}")
    yield
    ml_models.clear()


app = FastAPI(
    title="AI 供应链可视化风控智能微服务",
    description="面向大屏可视化的在线实时风险预警评分 + 独热特征工程对齐 + XAI 归因归纳 + 7天时序销量预测 API",
    version="2.0.0",
    lifespan=lifespan
)

class OrderInput(BaseModel):
    order_id: str
    order_amount: float             
    profit_ratio: float                  
    shipping_mode: str                  
    order_quantity: Optional[int] = 1
    scheduled_days: Optional[float] = 3.0
    order_city: Optional[str] = None
    category: Optional[str] = None
    order_status: Optional[str] = "PROCESSING"  

class ForecastInput(BaseModel):
    order_amount: float
    order_quantity: int
    shipping_mode: Optional[str] = "Standard Class"
    order_city: Optional[str] = None
    category: Optional[str] = None

def path_with_query(request: Request):
    query = request.scope.get("query_string", b"").decode("latin-1")
    return f"{request.url.path}?{query}" if query else request.url.path

def build_signature(method, path_query, body, timestamp, secret):
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join([SIGNATURE_VERSION, method.upper(), path_query, timestamp, body_hash])
    digest = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{SIGNATURE_VERSION}={digest}"

async def verify_service_auth(request: Request):
    expected_api_key = os.getenv("AI_SERVICE_API_KEY", "")
    hmac_secret = os.getenv("AI_SERVICE_HMAC_SECRET", "")
    if not expected_api_key and not hmac_secret:
        return

    if expected_api_key:
        provided_api_key = request.headers.get(API_KEY_HEADER)
        if not provided_api_key or not hmac.compare_digest(provided_api_key, expected_api_key):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    if not hmac_secret:
        return

    timestamp = request.headers.get(TIMESTAMP_HEADER)
    provided_signature = request.headers.get(SIGNATURE_HEADER)
    if not timestamp or not provided_signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing request signature")

    try:
        timestamp_seconds = int(float(timestamp))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature timestamp")

    max_age_seconds = int(os.getenv("REQUEST_SIGNATURE_MAX_AGE_SECONDS", "300"))
    if max_age_seconds > 0 and abs(time.time() - timestamp_seconds) > max_age_seconds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired request signature")

    body = await request.body()
    expected_signature = build_signature(request.method, path_with_query(request), body, timestamp, hmac_secret)
    if not hmac.compare_digest(provided_signature, expected_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid request signature")

CITY_WEALTH_MAP = {
    'San Jose': 0.98, 'San Francisco': 0.97, 'Seattle': 0.95, 'New York': 0.94,
    'Boston': 0.93, 'Washington': 0.92, 'Austin': 0.90, 'Denver': 0.88,
    'Los Angeles': 0.87, 'Chicago': 0.85, 'Dallas': 0.84, 'Houston': 0.83,
    'Atlanta': 0.82, 'Miami': 0.81, 'Portland': 0.80,
}

def get_wealth_score(city_name):
    if not city_name:
        return 0.5
    for key, score in CITY_WEALTH_MAP.items():
        if key.lower() in str(city_name).lower():
            return score
    return 0.5

def build_full_feature_row(
    order_amount, profit_per_order, shipping_mode_encoded,
    scheduled_days, city_wealth_score, order_month, order_weekday,
    category, order_status, feature_list
):
    """
    根据离线训练时导出的特征白皮书清单，动态生成一行标准 DataFrame。
    将对应的独热编码(One-Hot)字段精准“点亮”标记为 1。
    """
    row = {f: 0 for f in feature_list}

    mapping = {
        'Order Item Total': order_amount,
        'Order Profit Per Order': profit_per_order,
        'Shipping Mode_encoded': shipping_mode_encoded,
        'Days for shipment (scheduled)': scheduled_days,
        'city_wealth_score': city_wealth_score,
        'order_month': order_month,
        'order_weekday': order_weekday,
    }
    for k, v in mapping.items():
        if k in row:
            row[k] = v

    if category:
        cat_col = f"cat_{category}"
        if cat_col in row:
            row[cat_col] = 1
        else:
            if "cat_Other" in row:
                row["cat_Other"] = 1

    if order_status:
        status_col = f"status_{order_status}"
        if status_col in row:
            row[status_col] = 1

    if profit_per_order <= -10: bucket = '亏损'
    elif profit_per_order <= 0: bucket = '微利'
    elif profit_per_order <= 50: bucket = '正常'
    else: bucket = '高利润'
    
    profit_col = f"profit_{bucket}"
    if profit_col in row:
        row[profit_col] = 1

    return pd.DataFrame([row])

@app.post("/predict/risk", summary="在线订单风险拦截与可解释性归因分析")
async def predict_risk(data: OrderInput, _: None = Depends(verify_service_auth)):
    if "risk" not in ml_models:
        raise HTTPException(status_code=500, detail="风险大脑模型未正常装载")

    try:
        encoded_mode = int(ml_models["encoder"].transform([data.shipping_mode])[0])
    except Exception:
        encoded_mode = 0

    profit_per_order = data.order_amount * data.profit_ratio
    city_wealth = get_wealth_score(data.order_city)
    now = datetime.now()

    if "risk_features" in ml_models:
        input_df = build_full_feature_row(
            order_amount=data.order_amount,
            profit_per_order=profit_per_order,
            shipping_mode_encoded=encoded_mode,
            scheduled_days=data.scheduled_days or 3.0,
            city_wealth_score=city_wealth,
            order_month=now.month,
            order_weekday=now.weekday(),
            category=data.category,
            order_status=data.order_status,
            feature_list=ml_models["risk_features"]
        )
    else:
        input_df = pd.DataFrame([{'Order Item Total': data.order_amount, 'Order Profit Per Order': profit_per_order, 'Shipping Mode_encoded': encoded_mode}])

    risk_prob = float(ml_models["risk"].predict_proba(input_df)[0][1])
    is_high_risk = risk_prob > 0.85

    importances = ml_models["risk"].feature_importances_
    feature_names = ml_models.get("risk_features", ['订单金额贡献度', '利润率贡献度', '运输模式敏感度'])
    
    importance_pairs = sorted(list(zip(feature_names, importances)), key=lambda x: x[1], reverse=True)
    top5_xai = {name: round(float(score), 4) for name, score in importance_pairs[:5]}

    risk_reasons = []
    if profit_per_order < 0: risk_reasons.append("订单初始利润为负，属于严重的倒贴亏损订单")
    if city_wealth < 0.3: risk_reasons.append("收货目的地城市经济总分处于低水平，有潜在延期结款坏账隐患")
    if data.shipping_mode == "Same Day" and data.profit_ratio < 0.05: risk_reasons.append("紧急当日送达配额被低利润业务占用，导致供应链挤兑风险")
    if not risk_reasons: risk_reasons.append("多特征协同评估：触发组合逻辑风控预警")

    res = {
        "risk_score": round(risk_prob, 4),
        "risk_percentage": f"{risk_prob * 100:.1f}%",
        "is_high_risk": is_high_risk,
        "risk_level": "高风险拦截" if risk_prob > 0.85 else ("中度关注" if risk_prob > 0.5 else "绿色安全"),
        "risk_reasons": risk_reasons,
        "xai_analysis": {
            "explain_method": "RandomForest MLOps Feature Importance Analysis",
            "top_features_attribution": top5_xai,
            "business_note": "该权重代表系统训练时对各类事件判罚的敏感程度（归因百分比）"
        }
    }

    if is_high_risk:
        res["alert_detail"] = {
            "order_id": data.order_id,
            "risk_type": "供应链高欺诈/异常风险",
            "probability": round(risk_prob, 4),
            "timestamp": datetime.now().isoformat()
        }

    return res


@app.get("/api/v1/forecast", summary="未来7天销量趋势预测折线图接口（GET版）")
async def forecast_7days(
    order_amount: float = 100.0,
    order_quantity: int = 1,
    shipping_mode: str = "Standard Class",
    order_city: Optional[str] = None,
    category: Optional[str] = None,
    _: None = Depends(verify_service_auth)
):
    if "sales" not in ml_models:
        raise HTTPException(status_code=500, detail="时序销量回归预测大脑尚未苏醒")

    try:
        encoded_mode = int(ml_models["encoder"].transform([shipping_mode])[0])
    except Exception:
        encoded_mode = 0

    city_wealth = get_wealth_score(order_city)
    now = datetime.now()
    forecast_list = []

    sales_features = ml_models.get("sales_features", ['Order Item Total', 'Order Item Quantity', 'city_wealth_score', 'Shipping Mode_encoded'])

    for i in range(7):
        future_date = now + timedelta(days=i + 1)

        row = {f: 0 for f in sales_features}
        mapping = {
            'Order Item Total': order_amount,
            'Order Item Quantity': order_quantity,
            'Shipping Mode_encoded': encoded_mode,
            'city_wealth_score': city_wealth,
        }
        row.update({k: v for k, v in mapping.items() if k in row})
        if 'order_month' in row: row['order_month'] = future_date.month
        if 'order_weekday' in row: row['order_weekday'] = future_date.weekday()

        if category:
            cat_col = f"cat_{category}"
            if cat_col in row: row[cat_col] = 1
            elif "cat_Other" in row: row["cat_Other"] = 1

        input_df = pd.DataFrame([row])
        predicted_sales = float(ml_models["sales"].predict(input_df)[0])
        predicted_sales = max(0, round(predicted_sales, 2))

        forecast_list.append({
            "date": future_date.strftime("%Y-%m-%d"),
            "day_index": f"第 {i + 1} 天",
            "predicted_sales_volume": predicted_sales,
            "weekday_en": future_date.strftime("%A")
        })

    total_7d = sum(item["predicted_sales_volume"] for item in forecast_list)

    return {
        "forecast_period": "未来连续 7 个自然日趋势探针预测",
        "base_date": now.strftime("%Y-%m-%d"),
        "total_predicted_sales_aggregate": round(total_7d, 2),
        "avg_daily_sales_volume": round(total_7d / 7, 2),
        "trend_direction": "上扬成长" if forecast_list[-1]["predicted_sales_volume"] > forecast_list[0]["predicted_sales_volume"] else "平稳波动/周期回调",
        "daily_forecast_series": forecast_list
    }

@app.post("/predict/forecast", summary="未来7天销量预测（面向后端调用的 POST 强契约版）")
async def forecast_post(data: ForecastInput, _: None = Depends(verify_service_auth)):
    return await forecast_7days(
        order_amount=data.order_amount,
        order_quantity=data.order_quantity,
        shipping_mode=data.shipping_mode or "Standard Class",
        order_city=data.order_city,
        category=data.category
    )

@app.get("/health", summary="微服务心跳自检")
async def health_check():
    return {
        "status": "healthy",
        "loaded_models_manifest": list(ml_models.keys()),
        "microservice_time": datetime.now().isoformat()
    }
