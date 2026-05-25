from __future__ import annotations

import csv
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = SCRIPT_DIR / "dataset" / "DataCoSupplyChainDataset.csv"

CORE_FIELDS = [
    "Order Id",
    "order date (DateOrders)",
    "Shipping Mode",
    "Delivery Status",
    "Customer City",
    "Customer Country",
    "Latitude",
    "Longitude",
    "Category Name",
    "Product Name",
    "Sales",
    "Order Item Total",
    "Order Item Profit Ratio",
    "Order Profit Per Order",
    "Late_delivery_risk",
]


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {value!r}") from None


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"{name} must be a number, got {value!r}") from None


def clean_value(value: str | None) -> Any:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped != "" else None


def build_payload(row: dict[str, str]) -> dict[str, Any]:
    return {field: clean_value(row.get(field)) for field in CORE_FIELDS if field in row}


def post_order(session: requests.Session, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    response = session.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def main() -> int:
    ingest_url = os.getenv("BACKEND_INGEST_URL", "http://localhost:8000/api/v1/stream/ingest")
    dataset_path = Path(os.getenv("DATASET_PATH", str(DEFAULT_DATASET)))
    row_limit = env_int("ROW_LIMIT", 100)
    start_offset = env_int("START_OFFSET", 0)
    replay_rate = env_float("REPLAY_RATE", 5.0)
    request_timeout = env_float("REQUEST_TIMEOUT_SECONDS", 5.0)

    if replay_rate <= 0:
        raise ValueError("REPLAY_RATE must be greater than 0")
    if row_limit <= 0:
        raise ValueError("ROW_LIMIT must be greater than 0")
    if start_offset < 0:
        raise ValueError("START_OFFSET must be greater than or equal to 0")
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    sleep_seconds = 1.0 / replay_rate
    attempted = 0
    sent = 0
    failed = 0

    print(f"[replay] dataset={dataset_path}")
    print(f"[replay] ingest_url={ingest_url}")
    print(f"[replay] row_limit={row_limit} start_offset={start_offset} replay_rate={replay_rate} rows/s")

    with requests.Session() as session:
        session.trust_env = False
        with dataset_path.open("r", encoding="ISO-8859-1", newline="") as file:
            reader = csv.DictReader(file)

            for index, row in enumerate(reader):
                if index < start_offset:
                    continue
                if attempted >= row_limit:
                    break

                payload = build_payload(row)
                order_id = payload.get("Order Id", f"row-{index}")
                attempted += 1

                try:
                    result = post_order(session, ingest_url, payload, request_timeout)
                    sent += 1
                    risk_score = result.get("risk_score")
                    is_high_risk = result.get("is_high_risk")
                    print(
                        f"[replay] sent={sent} order_id={order_id} "
                        f"risk_score={risk_score} high_risk={is_high_risk}"
                    )
                except requests.RequestException as exc:
                    failed += 1
                    print(f"[replay] failed order_id={order_id} error={exc}", file=sys.stderr)

                time.sleep(sleep_seconds)

    print(f"[replay] finished attempted={attempted} sent={sent} failed={failed}")
    return 0 if sent > 0 and failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
