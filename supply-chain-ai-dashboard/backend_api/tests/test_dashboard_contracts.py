from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend_api.app.db import database
from backend_api.app.schemas import OrderIngestRequest


class DashboardContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)
        database.Base.metadata.create_all(bind=self.engine)
        self.session = self.session_factory()

    def tearDown(self) -> None:
        self.session.close()
        database.Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_dataco_fields_are_normalized_for_ai_features(self) -> None:
        request = OrderIngestRequest.model_validate(
            {
                "Order Id": 20257,
                "Order City": "Seattle",
                "Order Country": "United States",
                "Order Status": "COMPLETE",
                "Order Item Quantity": "3",
                "Days for shipment (scheduled)": "2",
                "Order Item Total": "129.90",
            }
        )

        self.assertEqual(request.order_id, "20257")
        self.assertEqual(request.order_city, "Seattle")
        self.assertEqual(request.order_country, "United States")
        self.assertEqual(request.order_status, "COMPLETE")
        self.assertEqual(request.order_quantity, 3)
        self.assertEqual(request.scheduled_days, 2)

    def test_order_destination_fields_are_persisted(self) -> None:
        request = OrderIngestRequest.model_validate(
            {
                "Order Id": "A-1",
                "Customer City": "Miami",
                "Customer Country": "EE. UU.",
                "Order City": "Seattle",
                "Order Country": "United States",
                "Order Status": "COMPLETE",
                "Order Item Quantity": 4,
                "Days for shipment (scheduled)": 3,
                "Order Item Total": 80,
            }
        )

        record = database.upsert_order(self.session, request, risk_score=0.2)

        self.assertEqual(record.order_city, "Seattle")
        self.assertEqual(record.order_country, "United States")
        self.assertEqual(record.order_status, "COMPLETE")
        self.assertEqual(record.order_quantity, 4)
        self.assertEqual(float(record.scheduled_days), 3.0)

    def test_realtime_kpi_heatmap_prefers_order_destination(self) -> None:
        first = OrderIngestRequest.model_validate(
            {
                "Order Id": "A-1",
                "Customer City": "Miami",
                "Customer Country": "EE. UU.",
                "Order City": "Seattle",
                "Order Country": "United States",
                "Order Item Total": 20,
            }
        )
        second = OrderIngestRequest.model_validate(
            {
                "Order Id": "A-2",
                "Customer City": "Miami",
                "Customer Country": "EE. UU.",
                "Order City": "Seattle",
                "Order Country": "United States",
                "Order Item Total": 30,
            }
        )

        database.upsert_order(self.session, first, risk_score=0.1)
        database.upsert_order(self.session, second, risk_score=0.1)

        kpi = database.get_realtime_kpi(self.session)

        self.assertEqual(kpi.totalOrders, 2)
        self.assertEqual(kpi.gmv, 50.0)
        self.assertEqual(kpi.heatMap[0], {"name": "Seattle", "value": 2})
        self.assertIn({"name": "Washington", "value": 2}, kpi.regionHeatMap)

    def test_alert_xai_and_forecast_fallback_contracts(self) -> None:
        request = OrderIngestRequest.model_validate({"Order Id": "A-1", "Order Item Total": 100})
        database.upsert_order(self.session, request, risk_score=0.9)
        alert = database.create_alert(
            session=self.session,
            order_id="A-1",
            risk_type="供应链高欺诈/异常风险",
            probability=0.91,
            xai_analysis={"Order Profit Per Order": 0.42},
        )

        response = database.alert_to_response(alert)
        forecast = database.build_forecast_fallback(self.session)

        self.assertEqual(response.xai_analysis, {"Order Profit Per Order": 0.42})
        self.assertEqual(len(forecast.days), 7)
        self.assertEqual(len(forecast.values), 7)
        self.assertEqual(forecast.source, "history-fallback")


if __name__ == "__main__":
    unittest.main()
