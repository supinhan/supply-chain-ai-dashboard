from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


FIELD_ALIASES = {
    "Order Id": "order_id",
    "order date (DateOrders)": "order_date",
    "Shipping Mode": "shipping_mode",
    "Delivery Status": "delivery_status",
    "Customer City": "customer_city",
    "Customer Country": "customer_country",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "Category Name": "product_category",
    "Product Name": "product_name",
    "Order Item Total": "order_amount",
    "Sales": "order_amount",
    "Order Item Profit Ratio": "profit_ratio",
    "Order Profit Per Order": "order_profit",
    "Late_delivery_risk": "late_delivery_risk",
}


class OrderIngestRequest(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    order_id: str = Field(min_length=1, max_length=64)
    order_date: datetime | None = None
    shipping_mode: str | None = Field(default=None, max_length=64)
    delivery_status: str | None = Field(default=None, max_length=64)
    customer_city: str | None = Field(default=None, max_length=128)
    customer_country: str | None = Field(default=None, max_length=128)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    product_category: str | None = Field(default=None, max_length=128)
    product_name: str | None = Field(default=None, max_length=256)
    order_amount: float = Field(default=0, ge=0)
    profit_ratio: float | None = Field(default=None, ge=-10, le=10)
    order_profit: float | None = None
    late_delivery_risk: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_dataco_fields(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw

        normalized = dict(raw)
        for source, target in FIELD_ALIASES.items():
            if source in raw and target not in normalized:
                normalized[target] = raw[source]
        return normalized

    @field_validator("order_id", mode="before")
    @classmethod
    def stringify_order_id(cls, value: Any) -> str:
        return str(value).strip()

    @field_validator("order_date", mode="before")
    @classmethod
    def parse_order_date(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        for fmt in ("%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(str(value), fmt)
            except ValueError:
                continue
        return value

    @field_validator("late_delivery_risk", mode="before")
    @classmethod
    def parse_boolish(cls, value: Any) -> bool | None:
        if value in (None, ""):
            return None
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y"}


class RiskPrediction(BaseModel):
    risk_score: float = Field(ge=0, le=1)
    is_high_risk: bool
    risk_type: str = "高延迟风险"
    xai_analysis: dict[str, float] = Field(default_factory=dict)


class AlertResponse(BaseModel):
    id: int | None = None
    order_id: str
    risk_type: str
    probability: float
    status: int = 0
    timestamp: datetime


class KPIResponse(BaseModel):
    totalOrders: int = 0
    gmv: float = 0
    otdRate: float = 0
    riskCount: int = 0
    delayRate: float = 0
    heatMap: list[dict[str, Any]] = Field(default_factory=list)


class HistoryPoint(BaseModel):
    bucket: str
    order_count: int
    risk_count: int
    gmv: float


class IngestResponse(BaseModel):
    status: str = "success"
    order_id: str
    risk_score: float
    is_high_risk: bool
    alert: AlertResponse | None = None


class WebSocketEnvelope(BaseModel):
    type: str
    data: Any
