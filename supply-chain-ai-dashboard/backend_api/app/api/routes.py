from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.security import RequestAuthError, verify_request_auth
from ..db.database import (
    alert_to_response,
    build_forecast_fallback,
    create_alert,
    get_history,
    get_recent_alerts,
    get_realtime_kpi,
    get_session,
    upsert_order,
)
from ..schemas import ForecastResponse, IngestResponse, KPIResponse, OrderIngestRequest
from ..services.cache import cache_client
from ..services.model_runner import risk_model_runner
from ..ws.manager import websocket_manager


router = APIRouter(prefix=settings.api_prefix)


def _path_with_query(request: Request) -> str:
    query = request.scope.get("query_string", b"").decode("latin-1")
    return f"{request.url.path}?{query}" if query else request.url.path


async def verify_ingest_auth(request: Request) -> None:
    body = await request.body()
    try:
        verify_request_auth(
            request.method,
            _path_with_query(request),
            body,
            request.headers,
            expected_api_key=settings.ingest_api_key,
            secret=settings.ingest_hmac_secret,
            max_age_seconds=settings.request_signature_max_age_seconds,
        )
    except RequestAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/stream/ingest", response_model=IngestResponse)
async def ingest_order(
    payload: OrderIngestRequest,
    _: None = Depends(verify_ingest_auth),
    session: Session = Depends(get_session),
) -> IngestResponse:
    prediction = await risk_model_runner.predict(payload)
    upsert_order(session, payload, prediction.risk_score)

    alert_payload = None
    if prediction.is_high_risk:
        alert = create_alert(
            session=session,
            order_id=payload.order_id,
            risk_type=prediction.risk_type,
            probability=prediction.risk_score,
            xai_analysis=prediction.xai_analysis,
        )
        alert_payload = alert_to_response(alert)
        alert_message = {
            "type": "alert",
            "data": {
                "id": alert_payload.id,
                "orderId": alert_payload.order_id,
                "riskType": alert_payload.risk_type,
                "probability": alert_payload.probability,
                "level": "danger",
                "icon": "fas fa-exclamation-circle",
                "timestamp": alert_payload.timestamp.isoformat(),
                "xai_analysis": alert_payload.xai_analysis,
            },
        }
        await cache_client.publish_alert(alert_message)
        await websocket_manager.broadcast(alert_message)

    stats_message = {"type": "stats", "data": get_realtime_kpi(session).model_dump()}
    await cache_client.set_kpi(stats_message["data"])
    await websocket_manager.broadcast(stats_message)
    return IngestResponse(
        order_id=payload.order_id,
        risk_score=prediction.risk_score,
        is_high_risk=prediction.is_high_risk,
        alert=alert_payload,
    )


@router.get("/kpi/realtime", response_model=KPIResponse)
async def realtime_kpi(session: Session = Depends(get_session)) -> KPIResponse:
    return get_realtime_kpi(session)


@router.get("/kpi/history")
async def kpi_history(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    session: Session = Depends(get_session),
) -> dict:
    return {"hours": hours, "items": [item.model_dump() for item in get_history(session, hours)]}


@router.get("/forecast", response_model=ForecastResponse)
async def forecast(
    order_amount: float = Query(default=100.0, ge=0),
    order_quantity: int = Query(default=1, ge=0),
    shipping_mode: str = Query(default="Standard Class", max_length=64),
    order_city: str | None = Query(default=None, max_length=128),
    category: str | None = Query(default=None, max_length=128),
    session: Session = Depends(get_session),
) -> ForecastResponse:
    remote_forecast = await risk_model_runner.forecast(
        order_amount=order_amount,
        order_quantity=order_quantity,
        shipping_mode=shipping_mode,
        order_city=order_city,
        category=category,
    )
    return remote_forecast or build_forecast_fallback(session)


@router.get("/alerts/recent")
async def recent_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict:
    return {"items": [item.model_dump(mode="json") for item in get_recent_alerts(session, limit)]}


@router.websocket("/ws/alerts")
async def alerts_socket(websocket: WebSocket) -> None:
    await websocket_manager.connect(websocket)
    session = next(get_session())
    try:
        await websocket.send_json({"type": "stats", "data": get_realtime_kpi(session).model_dump()})
        for alert in get_recent_alerts(session, limit=10):
            await websocket.send_json(
                {
                    "type": "alert",
                    "data": {
                        "id": alert.id,
                        "orderId": alert.order_id,
                        "riskType": alert.risk_type,
                        "probability": alert.probability,
                        "level": "danger",
                        "icon": "fas fa-exclamation-circle",
                        "timestamp": alert.timestamp.isoformat(),
                        "xai_analysis": alert.xai_analysis,
                    },
                }
            )

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    finally:
        session.close()
