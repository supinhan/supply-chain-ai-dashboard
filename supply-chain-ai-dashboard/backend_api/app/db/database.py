from __future__ import annotations

import ast
import json
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Generator

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    func,
    inspect,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from ..core.config import Settings, settings
from ..schemas import AlertResponse, ForecastResponse, HistoryPoint, KPIResponse, OrderIngestRequest
from ..services.geo_mapping import aggregate_region_heat_map


class Base(DeclarativeBase):
    pass


class OrderRecord(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    order_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    shipping_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_city: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    customer_country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    order_city: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    order_country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    order_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    product_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    order_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    order_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scheduled_days: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    profit_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    late_delivery_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AlertRecord(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    risk_type: Mapped[str] = mapped_column(String(64), default="高延迟风险")
    probability: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    status: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


def build_engine(config: Settings = settings):
    connect_args = {"check_same_thread": False} if config.database_url.startswith("sqlite") else {}
    return create_engine(config.database_url, pool_pre_ping=True, connect_args=connect_args)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_order_columns()


def _ensure_order_columns() -> None:
    """Keep existing demo databases compatible with newly ingested DataCo fields."""
    inspector = inspect(engine)
    if "orders" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("orders")}
    missing_columns = [
        column
        for column in OrderRecord.__table__.columns
        if column.name not in existing_columns
    ]
    if not missing_columns:
        return

    dialect = engine.dialect.name
    type_compiler = engine.dialect.type_compiler
    with engine.begin() as connection:
        for column in missing_columns:
            sql_type = type_compiler.process(column.type)
            if dialect == "mysql":
                statement = text(f"ALTER TABLE orders ADD COLUMN `{column.name}` {sql_type} NULL")
            else:
                statement = text(f'ALTER TABLE orders ADD COLUMN "{column.name}" {sql_type}')
            connection.execute(statement)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _decimal_or_none(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _normalized_payload(payload: OrderIngestRequest) -> dict[str, Any]:
    extra_fields = set(payload.model_extra or {})
    return payload.model_dump(mode="json", exclude_none=True, exclude=extra_fields)


def upsert_order(session: Session, payload: OrderIngestRequest, risk_score: float) -> OrderRecord:
    existing = session.scalar(select(OrderRecord).where(OrderRecord.order_id == payload.order_id))
    record = existing or OrderRecord(order_id=payload.order_id)

    record.order_date = payload.order_date
    record.shipping_mode = payload.shipping_mode
    record.delivery_status = payload.delivery_status
    record.customer_city = payload.customer_city
    record.customer_country = payload.customer_country
    record.order_city = payload.order_city
    record.order_country = payload.order_country
    record.order_status = payload.order_status
    record.latitude = _decimal_or_none(payload.latitude)
    record.longitude = _decimal_or_none(payload.longitude)
    record.product_category = payload.product_category
    record.product_name = payload.product_name
    record.order_amount = Decimal(str(payload.order_amount or 0))
    record.order_quantity = payload.order_quantity
    record.scheduled_days = _decimal_or_none(payload.scheduled_days)
    record.profit_ratio = _decimal_or_none(payload.profit_ratio)
    record.risk_score = Decimal(str(round(risk_score, 4)))
    record.late_delivery_risk = bool(payload.late_delivery_risk)
    record.raw_payload = _normalized_payload(payload)

    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_alert(
    session: Session,
    order_id: str,
    risk_type: str,
    probability: float,
    detail: str | None = None,
    xai_analysis: dict[str, Any] | None = None,
) -> AlertRecord:
    if detail is None and xai_analysis is not None:
        detail = json.dumps({"xai_analysis": xai_analysis}, ensure_ascii=False)

    record = AlertRecord(
        order_id=order_id,
        risk_type=risk_type,
        probability=Decimal(str(round(probability, 4))),
        detail=detail,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def _parse_alert_detail(detail: str | None) -> dict[str, Any]:
    if not detail:
        return {}

    parsed: Any
    try:
        parsed = json.loads(detail)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(detail)
        except (SyntaxError, ValueError):
            return {}

    if not isinstance(parsed, dict):
        return {}

    xai_analysis = parsed.get("xai_analysis", parsed)
    return xai_analysis if isinstance(xai_analysis, dict) else {}


def alert_to_response(record: AlertRecord) -> AlertResponse:
    return AlertResponse(
        id=record.id,
        order_id=record.order_id,
        risk_type=record.risk_type,
        probability=float(record.probability),
        status=record.status,
        timestamp=record.created_at,
        xai_analysis=_parse_alert_detail(record.detail),
    )


def get_realtime_kpi(session: Session) -> KPIResponse:
    total_orders = session.scalar(select(func.count(OrderRecord.id))) or 0
    total_gmv = session.scalar(select(func.coalesce(func.sum(OrderRecord.order_amount), 0))) or 0
    risk_count = session.scalar(select(func.count(AlertRecord.id))) or 0
    late_count = session.scalar(select(func.count(OrderRecord.id)).where(OrderRecord.late_delivery_risk.is_(True))) or 0
    on_time_count = max(int(total_orders) - int(late_count), 0)
    otd_rate = (on_time_count / int(total_orders) * 100) if total_orders else 0
    delay_rate = (int(late_count) / int(total_orders) * 100) if total_orders else 0

    location_city = func.coalesce(OrderRecord.order_city, OrderRecord.customer_city).label("city")
    location_country = func.coalesce(OrderRecord.order_country, OrderRecord.customer_country).label("country")
    heat_rows = session.execute(
        select(location_city, location_country, func.count(OrderRecord.id))
        .where(location_city.is_not(None))
        .group_by(location_city, location_country)
        .order_by(func.count(OrderRecord.id).desc())
    ).all()
    heat_map = [{"name": row[0], "value": int(row[2])} for row in heat_rows[:20] if row[0]]
    region_heat_map, heat_map_meta = aggregate_region_heat_map(heat_rows)

    # 计算订单状态分布 (已完成/运输中/待发货)
    status_counts: dict[str, int] = defaultdict(int)
    status_rows = session.execute(
        select(func.coalesce(OrderRecord.order_status, OrderRecord.delivery_status), func.count(OrderRecord.id))
        .group_by(func.coalesce(OrderRecord.order_status, OrderRecord.delivery_status))
    ).all()

    for status, count in status_rows:
        if not status:
            status_counts["待发货"] += int(count)
            continue
        status_lower = str(status).lower()
        if "complete" in status_lower or "closed" in status_lower or "on time" in status_lower or "advance" in status_lower:
            status_counts["已完成"] += int(count)
        elif "late" in status_lower or "processing" in status_lower or "pending" in status_lower:
            status_counts["运输中"] += int(count)
        else:
            status_counts["待发货"] += int(count)

    order_status = [
        {"value": status_counts["已完成"], "name": "已完成", "itemStyle": {"color": "#91cc75"}},
        {"value": status_counts["运输中"], "name": "运输中", "itemStyle": {"color": "#5470c6"}},
        {"value": status_counts["待发货"], "name": "待发货", "itemStyle": {"color": "#fac858"}},
    ]

    return KPIResponse(
        totalOrders=int(total_orders),
        gmv=float(total_gmv),
        otdRate=round(otd_rate, 2),
        riskCount=int(risk_count),
        delayRate=round(delay_rate, 2),
        heatMap=heat_map,
        regionHeatMap=region_heat_map,
        heatMapMeta=heat_map_meta,
        orderStatus=order_status,
    )



def get_history(session: Session, hours: int = 24) -> list[HistoryPoint]:
    since = datetime.utcnow() - timedelta(hours=hours)
    orders = session.scalars(
        select(OrderRecord)
        .where(OrderRecord.created_at >= since)
        .order_by(OrderRecord.created_at.asc())
        .limit(10000)
    ).all()

    alert_counts = dict(
        session.execute(
            select(AlertRecord.order_id, func.count(AlertRecord.id))
            .where(AlertRecord.created_at >= since)
            .group_by(AlertRecord.order_id)
        ).all()
    )

    buckets: dict[str, dict[str, float | int]] = defaultdict(lambda: {"order_count": 0, "risk_count": 0, "gmv": 0.0})
    for order in orders:
        bucket = order.created_at.replace(minute=0, second=0, microsecond=0).isoformat()
        buckets[bucket]["order_count"] = int(buckets[bucket]["order_count"]) + 1
        buckets[bucket]["risk_count"] = int(buckets[bucket]["risk_count"]) + int(alert_counts.get(order.order_id, 0))
        buckets[bucket]["gmv"] = float(buckets[bucket]["gmv"]) + float(order.order_amount or 0)

    return [
        HistoryPoint(
            bucket=bucket,
            order_count=int(values["order_count"]),
            risk_count=int(values["risk_count"]),
            gmv=round(float(values["gmv"]), 2),
        )
        for bucket, values in sorted(buckets.items())
    ]


def get_recent_alerts(session: Session, limit: int = 50) -> list[AlertResponse]:
    rows = session.scalars(select(AlertRecord).order_by(AlertRecord.created_at.desc()).limit(limit)).all()
    return [alert_to_response(row) for row in rows]


def build_forecast_fallback(session: Session, days: int = 7) -> ForecastResponse:
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    orders = session.scalars(
        select(OrderRecord)
        .where(OrderRecord.created_at >= since)
        .order_by(OrderRecord.created_at.asc())
        .limit(10000)
    ).all()

    avg_daily_volume = round((len(orders) / days), 2) if days else 0
    forecast_values = [avg_daily_volume for _ in range(days)]
    daily_series = []
    for index, value in enumerate(forecast_values, start=1):
        future_date = now + timedelta(days=index)
        daily_series.append(
            {
                "date": future_date.strftime("%Y-%m-%d"),
                "day_index": f"第 {index} 天",
                "predicted_sales_volume": value,
                "weekday_en": future_date.strftime("%A"),
            }
        )

    total = round(sum(forecast_values), 2)
    return ForecastResponse(
        days=[f"D+{index}" for index in range(1, days + 1)],
        values=forecast_values,
        daily_forecast_series=daily_series,
        total_predicted_sales_aggregate=total,
        avg_daily_sales_volume=round(total / days, 2) if days else 0,
        trend_direction="平稳波动/周期回调",
        source="history-fallback",
    )
