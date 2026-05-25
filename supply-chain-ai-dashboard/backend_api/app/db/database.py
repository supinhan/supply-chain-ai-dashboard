from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Generator

from sqlalchemy import JSON, Boolean, DateTime, Integer, Numeric, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from ..core.config import Settings, settings
from ..schemas import AlertResponse, HistoryPoint, KPIResponse, OrderIngestRequest


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
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    product_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    order_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
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
    record.latitude = _decimal_or_none(payload.latitude)
    record.longitude = _decimal_or_none(payload.longitude)
    record.product_category = payload.product_category
    record.product_name = payload.product_name
    record.order_amount = Decimal(str(payload.order_amount or 0))
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
) -> AlertRecord:
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


def alert_to_response(record: AlertRecord) -> AlertResponse:
    return AlertResponse(
        id=record.id,
        order_id=record.order_id,
        risk_type=record.risk_type,
        probability=float(record.probability),
        status=record.status,
        timestamp=record.created_at,
    )


def get_realtime_kpi(session: Session) -> KPIResponse:
    total_orders = session.scalar(select(func.count(OrderRecord.id))) or 0
    total_gmv = session.scalar(select(func.coalesce(func.sum(OrderRecord.order_amount), 0))) or 0
    risk_count = session.scalar(select(func.count(AlertRecord.id))) or 0
    late_count = session.scalar(select(func.count(OrderRecord.id)).where(OrderRecord.late_delivery_risk.is_(True))) or 0
    on_time_count = max(int(total_orders) - int(late_count), 0)
    otd_rate = (on_time_count / int(total_orders) * 100) if total_orders else 0
    delay_rate = (int(late_count) / int(total_orders) * 100) if total_orders else 0

    heat_rows = session.execute(
        select(OrderRecord.customer_city, func.count(OrderRecord.id))
        .where(OrderRecord.customer_city.is_not(None))
        .group_by(OrderRecord.customer_city)
        .order_by(func.count(OrderRecord.id).desc())
        .limit(20)
    ).all()
    heat_map = [{"name": row[0], "value": int(row[1])} for row in heat_rows if row[0]]

    return KPIResponse(
        totalOrders=int(total_orders),
        gmv=float(total_gmv),
        otdRate=round(otd_rate, 2),
        riskCount=int(risk_count),
        delayRate=round(delay_rate, 2),
        heatMap=heat_map,
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
