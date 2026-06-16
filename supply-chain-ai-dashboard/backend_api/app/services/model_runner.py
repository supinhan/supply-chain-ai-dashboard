from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from ..core.config import Settings, settings
from ..core.security import build_auth_headers, canonical_path_with_query
from ..schemas import ForecastResponse, OrderIngestRequest, RiskPrediction


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
            try:
                return await self._predict_remote(order)
            except (httpx.HTTPError, AttributeError, KeyError, TypeError, ValueError):
                return self._predict_heuristic(order)
        if self.mode == "local" and self.local.model is not None:
            return self._predict_local(order)
        return self._predict_heuristic(order)

    async def _predict_remote(self, order: OrderIngestRequest) -> RiskPrediction:
        payload = {
            "order_id": order.order_id,
            "order_amount": order.order_amount,
            "profit_ratio": order.profit_ratio or 0,
            "shipping_mode": order.shipping_mode or "Standard Class",
            "order_quantity": order.order_quantity if order.order_quantity is not None else 1,
            "scheduled_days": order.scheduled_days if order.scheduled_days is not None else 3.0,
            "order_city": order.order_city or order.customer_city,
            "category": order.product_category,
            "order_status": order.order_status or order.delivery_status or "PROCESSING",
        }
        url = f"{self.config.ai_service_url}/predict/risk"
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            **build_auth_headers(
                "POST",
                canonical_path_with_query(url),
                body,
                api_key=self.config.ai_service_api_key,
                secret=self.config.ai_service_hmac_secret,
            ),
        }
        async with httpx.AsyncClient(timeout=self.config.request_timeout_seconds, trust_env=False) as client:
            response = await client.post(url, content=body, headers=headers)
            response.raise_for_status()
            data = response.json()

        score = max(0.0, min(float(data.get("risk_score", 0)), 1.0))
        xai_analysis = self._normalize_xai_analysis(data.get("xai_analysis", {}))
        return RiskPrediction(
            risk_score=score,
            is_high_risk=bool(data.get("is_high_risk", score >= self.config.risk_threshold)),
            risk_type=data.get("alert_detail", {}).get("risk_type", "高延迟风险"),
            xai_analysis=xai_analysis,
        )

    async def forecast(
        self,
        order_amount: float = 100.0,
        order_quantity: int = 1,
        shipping_mode: str = "Standard Class",
        order_city: str | None = None,
        category: str | None = None,
    ) -> ForecastResponse | None:
        if not self.config.ai_service_url:
            return None

        params = {
            "order_amount": order_amount,
            "order_quantity": order_quantity,
            "shipping_mode": shipping_mode,
            "order_city": order_city,
            "category": category,
        }
        params = {key: value for key, value in params.items() if value is not None}
        url = f"{self.config.ai_service_url}/api/v1/forecast"
        try:
            request_url = httpx.URL(url, params=params)
            path_with_query = request_url.raw_path.decode("ascii")
            headers = build_auth_headers(
                "GET",
                path_with_query,
                None,
                api_key=self.config.ai_service_api_key,
                secret=self.config.ai_service_hmac_secret,
            )
            async with httpx.AsyncClient(timeout=self.config.request_timeout_seconds, trust_env=False) as client:
                response = await client.get(request_url, headers=headers)
                response.raise_for_status()
                data = response.json()
            return self._normalize_forecast_response(data)
        except (httpx.HTTPError, AttributeError, KeyError, TypeError, ValueError):
            return None

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

    @staticmethod
    def _normalize_xai_analysis(raw: Any) -> dict[str, float]:
        if not isinstance(raw, dict):
            return {}

        candidate = raw.get("top_features_attribution", raw)
        if not isinstance(candidate, dict):
            return {}

        normalized: dict[str, float] = {}
        for feature, score in candidate.items():
            try:
                normalized[str(feature)] = round(float(score), 4)
            except (TypeError, ValueError):
                continue
        return normalized

    @staticmethod
    def _normalize_forecast_response(data: Any) -> ForecastResponse:
        if not isinstance(data, dict):
            raise ValueError("Forecast response must be a JSON object")

        series = data.get("daily_forecast_series")
        if not isinstance(series, list):
            series = []

        days = data.get("days")
        if not isinstance(days, list) or not days:
            days = [
                str(item.get("day_index") or item.get("date") or f"D+{index}")
                for index, item in enumerate(series, start=1)
                if isinstance(item, dict)
            ]

        values = data.get("values")
        if not isinstance(values, list) or not values:
            values = []
            for item in series:
                if not isinstance(item, dict):
                    continue
                try:
                    values.append(float(item.get("predicted_sales_volume", 0)))
                except (TypeError, ValueError):
                    values.append(0)

        def as_float(value: Any, default: float = 0) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        normalized_values: list[float] = []
        for value in values:
            normalized_values.append(as_float(value))
        total_default = sum(normalized_values) if normalized_values else 0
        average_default = (sum(normalized_values) / len(normalized_values)) if normalized_values else 0

        return ForecastResponse(
            days=[str(day) for day in days],
            values=normalized_values,
            daily_forecast_series=[item for item in series if isinstance(item, dict)],
            total_predicted_sales_aggregate=as_float(data.get("total_predicted_sales_aggregate"), total_default),
            avg_daily_sales_volume=as_float(data.get("avg_daily_sales_volume"), average_default),
            trend_direction=str(data.get("trend_direction", "平稳波动/周期回调")),
            source="ai-service",
        )


risk_model_runner = RiskModelRunner()
