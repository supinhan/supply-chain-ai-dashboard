from __future__ import annotations

import json
import unittest
from typing import Any, Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.app.api import routes
from backend_api.app.core import security
from backend_api.app.core.config import settings
from backend_api.app.db import database
from backend_api.app.main import app
from backend_api.app.schemas import ForecastResponse, OrderIngestRequest, RiskPrediction


class StubRunner:
    async def predict(self, order: OrderIngestRequest) -> RiskPrediction:
        return RiskPrediction(
            risk_score=0.93,
            is_high_risk=True,
            risk_type="供应链高欺诈/异常风险",
            xai_analysis={"Order Profit Per Order": 0.41, "city_wealth_score": 0.13},
        )

    async def forecast(self, **kwargs: Any) -> ForecastResponse | None:
        return None


class StubCache:
    async def set_kpi(self, payload: dict[str, Any]) -> None:
        return None

    async def publish_alert(self, payload: dict[str, Any]) -> None:
        return None


class StubWebSocketManager:
    async def broadcast(self, message: dict[str, Any]) -> None:
        return None


class ApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_security_settings = {
            "ingest_api_key": settings.ingest_api_key,
            "ingest_hmac_secret": settings.ingest_hmac_secret,
            "request_signature_max_age_seconds": settings.request_signature_max_age_seconds,
        }
        object.__setattr__(settings, "ingest_api_key", "")
        object.__setattr__(settings, "ingest_hmac_secret", "")
        object.__setattr__(settings, "request_signature_max_age_seconds", 300)

        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)
        database.Base.metadata.create_all(bind=self.engine)

        def override_session() -> Generator[Session, None, None]:
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

        self.original_runner = routes.risk_model_runner
        self.original_cache = routes.cache_client
        self.original_ws_manager = routes.websocket_manager
        routes.risk_model_runner = StubRunner()  # type: ignore[assignment]
        routes.cache_client = StubCache()  # type: ignore[assignment]
        routes.websocket_manager = StubWebSocketManager()  # type: ignore[assignment]
        app.dependency_overrides[database.get_session] = override_session
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        routes.risk_model_runner = self.original_runner
        routes.cache_client = self.original_cache
        routes.websocket_manager = self.original_ws_manager
        for key, value in self.original_security_settings.items():
            object.__setattr__(settings, key, value)
        database.Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_ingest_recent_alerts_kpi_and_forecast_routes(self) -> None:
        ingest_response = self.client.post(
            "/api/v1/stream/ingest",
            json={
                "Order Id": "R-1",
                "Order City": "Seattle",
                "Order Country": "United States",
                "Order Status": "COMPLETE",
                "Order Item Quantity": 2,
                "Days for shipment (scheduled)": 3,
                "Order Item Total": 120,
            },
        )
        self.assertEqual(ingest_response.status_code, 200)
        ingest_payload = ingest_response.json()
        self.assertTrue(ingest_payload["is_high_risk"])
        self.assertEqual(ingest_payload["alert"]["xai_analysis"]["Order Profit Per Order"], 0.41)

        alerts_response = self.client.get("/api/v1/alerts/recent?limit=5")
        self.assertEqual(alerts_response.status_code, 200)
        alerts_payload = alerts_response.json()
        self.assertEqual(alerts_payload["items"][0]["xai_analysis"]["city_wealth_score"], 0.13)

        kpi_response = self.client.get("/api/v1/kpi/realtime")
        self.assertEqual(kpi_response.status_code, 200)
        kpi_payload = kpi_response.json()
        self.assertEqual(kpi_payload["heatMap"][0], {"name": "Seattle", "value": 1})
        self.assertIn({"name": "Washington", "value": 1}, kpi_payload["regionHeatMap"])

        forecast_response = self.client.get("/api/v1/forecast")
        self.assertEqual(forecast_response.status_code, 200)
        forecast_payload = forecast_response.json()
        self.assertEqual(forecast_payload["source"], "history-fallback")
        self.assertEqual(len(forecast_payload["days"]), 7)

    def test_ingest_requires_valid_signature_when_configured(self) -> None:
        object.__setattr__(settings, "ingest_api_key", "replay-key")
        object.__setattr__(settings, "ingest_hmac_secret", "replay-secret")

        payload = {
            "Order Id": "SEC-1",
            "Order City": "Seattle",
            "Order Country": "United States",
            "Order Item Total": 120,
        }
        path = "/api/v1/stream/ingest"
        unsigned_response = self.client.post(path, json=payload)
        self.assertEqual(unsigned_response.status_code, 401)

        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        signed_headers = {
            "Content-Type": "application/json",
            **security.build_auth_headers(
                "POST",
                path,
                body,
                api_key="replay-key",
                secret="replay-secret",
            ),
        }
        signed_response = self.client.post(path, content=body, headers=signed_headers)
        self.assertEqual(signed_response.status_code, 200)
        self.assertEqual(signed_response.json()["order_id"], "SEC-1")


if __name__ == "__main__":
    unittest.main()
