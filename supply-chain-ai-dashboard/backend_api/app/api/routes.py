from __future__ import annotations

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db.database import (
    alert_to_response,
    create_alert,
    get_history,
    get_recent_alerts,
    get_realtime_kpi,
    get_session,
    upsert_order,
)
from ..schemas import IngestResponse, KPIResponse, OrderIngestRequest
from ..services.cache import cache_client
from ..services.model_runner import risk_model_runner
from ..ws.manager import websocket_manager


router = APIRouter(prefix=settings.api_prefix)


@router.post("/stream/ingest", response_model=IngestResponse)
async def ingest_order(
    payload: OrderIngestRequest,
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
            detail=str(prediction.xai_analysis),
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
                    },
                }
            )

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    finally:
        session.close()
