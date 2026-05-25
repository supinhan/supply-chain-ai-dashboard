from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..core.config import Settings, settings
from ..schemas import OrderIngestRequest, RiskPrediction


@dataclass
class LocalModelBundle:
    model: Any | None = None
    encoder: Any | None = None
    pandas: Any | None = None


class RiskModelRunner:
    def __init__(self, config: Settings = settings) -> None:
        self.config = config
        self.local = LocalModelBundle()
        self.mode = "heuristic"

    def load(self) -> None:
        if self.config.ai_service_url:
            self.mode = "remote"
            return

        if not self.config.local_model_path.exists():
            self.mode = "heuristic"
            return

        try:
            import joblib
            import pandas as pd

            self.local.model = joblib.load(self.config.local_model_path)
            self.local.encoder = (
                joblib.load(self.config.local_encoder_path)
                if self.config.local_encoder_path.exists()
                else None
            )
            self.local.pandas = pd
            self.mode = "local"
        except Exception:
            self.mode = "heuristic"

    async def predict(self, order: OrderIngestRequest) -> RiskPrediction:
        if self.mode == "remote":
            return await self._predict_remote(order)
        if self.mode == "local" and self.local.model is not None:
            return self._predict_local(order)
        return self._predict_heuristic(order)

    async def _predict_remote(self, order: OrderIngestRequest) -> RiskPrediction:
        payload = {
            "order_id": order.order_id,
            "order_amount": order.order_amount,
            "profit_ratio": order.profit_ratio or 0,
            "shipping_mode": order.shipping_mode or "Standard Class",
        }
        url = f"{self.config.ai_service_url}/predict/risk"
        async with httpx.AsyncClient(timeout=self.config.request_timeout_seconds) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        score = float(data.get("risk_score", 0))
        return RiskPrediction(
            risk_score=score,
            is_high_risk=bool(data.get("is_high_risk", score >= self.config.risk_threshold)),
            risk_type=data.get("alert_detail", {}).get("risk_type", "高延迟风险"),
            xai_analysis=data.get("xai_analysis", {}),
        )

    def _predict_local(self, order: OrderIngestRequest) -> RiskPrediction:
        shipping_mode = order.shipping_mode or "Standard Class"
        encoded_mode = 0
        if self.local.encoder is not None:
            try:
                encoded_mode = int(self.local.encoder.transform([shipping_mode])[0])
            except Exception:
                encoded_mode = 0

        profit = order.order_profit
        if profit is None:
            profit = (order.order_amount or 0) * (order.profit_ratio or 0)

        frame = self.local.pandas.DataFrame(
            [
                {
                    "Order Item Total": order.order_amount,
                    "Order Profit Per Order": profit,
                    "Shipping Mode_encoded": encoded_mode,
                }
            ]
        )
        score = float(self.local.model.predict_proba(frame)[0][1])
        importances = getattr(self.local.model, "feature_importances_", [])
        xai = {
            label: round(float(importances[index]), 3)
            for index, label in enumerate(["订单金额贡献度", "利润贡献度", "运输模式敏感度"])
            if index < len(importances)
        }
        return RiskPrediction(
            risk_score=round(score, 4),
            is_high_risk=score >= self.config.risk_threshold,
            risk_type="高延迟风险",
            xai_analysis=xai,
        )

    def _predict_heuristic(self, order: OrderIngestRequest) -> RiskPrediction:
        score = 0.08
        xai = {}

        if order.late_delivery_risk:
            score += 0.35
            xai["历史延迟标签"] = 0.35
        if order.profit_ratio is not None and order.profit_ratio < 0:
            score += 0.25
            xai["负利润订单"] = 0.25
        if order.delivery_status and "late" in order.delivery_status.lower():
            score += 0.2
            xai["配送状态异常"] = 0.2
        if order.order_amount >= 1000:
            score += 0.1
            xai["高金额订单"] = 0.1
        if order.shipping_mode and order.shipping_mode.lower() in {"same day", "first class"}:
            score += 0.08
            xai["高时效运输模式"] = 0.08

        score = min(round(score, 4), 0.99)
        return RiskPrediction(
            risk_score=score,
            is_high_risk=score >= self.config.risk_threshold,
            risk_type="高延迟风险",
            xai_analysis=xai,
        )


risk_model_runner = RiskModelRunner()
