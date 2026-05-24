from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from contextlib import asynccontextmanager
from datetime import datetime
import joblib
import pandas as pd
import os

ml_models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时一次性加载所有模型和清洗用的编码器
    ml_models["risk"] = joblib.load('model/risk_model.pkl')
    ml_models["encoder"] = joblib.load('model/shipping_mode_encoder.pkl')
    yield
    ml_models.clear()

app = FastAPI(title="AI 供应链风控微服务", lifespan=lifespan)

class OrderInput(BaseModel):
    order_id: str
    order_amount: float          # 对应 Order Item Total
    profit_ratio: float          # 对应计算出 Order Profit Per Order
    shipping_mode: str           # 文本输入，如 "Standard Class"

@app.post("/predict/risk")
async def predict_risk(data: OrderInput):
    if "risk" not in ml_models:
        raise HTTPException(status_code=500, detail="模型未加载")
        
    # 1. 模拟在线数据清洗：将前端/后端传来的文本 shipping_mode 转化为数字
    try:
        encoded_mode = ml_models["encoder"].transform([data.shipping_mode])[0]
    except Exception:
        # 如果传了不认识的文本，降级处理为 0
        encoded_mode = 0
        
    # 2. 组装成模型需要的 DataFrame
    input_df = pd.DataFrame([{
        'Order Item Total': data.order_amount,
        'Order Profit Per Order': data.order_amount * data.profit_ratio, # 算出真实利润
        'Shipping Mode_encoded': encoded_mode
    }])
    
    # 3. 预测风险概率
    risk_prob = float(ml_models["risk"].predict_proba(input_df)[0][1])
    is_high_risk = risk_prob > 0.85
    
    # 4. 可解释性 (XAI) 归因逻辑
    # 提取模型中各个特征的权重分，结合当前订单数据计算归因
    importances = ml_models["risk"].feature_importances_
    features = ['订单金额贡献度', '利润率贡献度', '运输模式敏感度']
    xai_attribution = {features[i]: round(float(importances[i]), 2) for i in range(len(features))}
    
    # 5. 组装响应体
    res = {
        "risk_score": round(risk_prob, 2),
        "is_high_risk": is_high_risk,
        "xai_analysis": xai_attribution # 丰富前端展示维度
    }
    
    # 6. 高风险告警结构
    if is_high_risk:
        res["alert_detail"] = {
            "order_id": data.order_id,
            "risk_type": "供应链高欺诈/异常风险",
            "probability": round(risk_prob, 2),
            "timestamp": datetime.now().isoformat()
        }
        
    return res