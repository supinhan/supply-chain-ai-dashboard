from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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
    "Order City",
    "Order Country",
    "Order Status",
    "Latitude",
    "Longitude",
    "Category Name",
    "Product Name",
    "Sales",
    "Order Item Total",
    "Order Item Quantity",
    "Days for shipment (scheduled)",
    "Order Item Profit Ratio",
    "Order Profit Per Order",
    "Late_delivery_risk",
]

API_KEY_HEADER = "X-SCAI-API-Key"
TIMESTAMP_HEADER = "X-SCAI-Timestamp"
SIGNATURE_HEADER = "X-SCAI-Signature"
SIGNATURE_VERSION = "v1"


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


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def clean_value(value: str | None) -> Any:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped != "" else None


def build_payload(row: dict[str, str]) -> dict[str, Any]:
    return {field: clean_value(row.get(field)) for field in CORE_FIELDS if field in row}


def read_checkpoint(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        row_index = payload.get("last_successful_row_index")
        return int(row_index) if row_index is not None else None
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def write_checkpoint(path: Path, row_index: int, order_id: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_successful_row_index": row_index,
        "last_successful_order_id": order_id,
        "updated_at_epoch": round(time.time(), 3),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_failed_log(path: Path, row_index: int, order_id: Any, error: Exception, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "row_index": row_index,
        "order_id": order_id,
        "error": str(error),
        "payload": payload,
        "failed_at_epoch": round(time.time(), 3),
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def should_retry_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


def canonical_path_with_query(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path or "/"
    return f"{path}?{parts.query}" if parts.query else path


def build_auth_headers(
    method: str,
    url: str,
    body: bytes,
    api_key: str = "",
    hmac_secret: str = "",
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if api_key:
        headers[API_KEY_HEADER] = api_key
    if not hmac_secret:
        return headers

    timestamp = str(int(time.time()))
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join(
        [
            SIGNATURE_VERSION,
            method.upper(),
            canonical_path_with_query(url),
            timestamp,
            body_hash,
        ]
    )
    digest = hmac.new(hmac_secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    headers[TIMESTAMP_HEADER] = timestamp
    headers[SIGNATURE_HEADER] = f"{SIGNATURE_VERSION}={digest}"
    return headers


def post_order(
    session: requests.Session,
    url: str,
    payload: dict[str, Any],
    timeout: float,
    max_retries: int,
    retry_backoff: float,
    api_key: str = "",
    hmac_secret: str = "",
) -> tuple[dict[str, Any], int]:
    attempt = 0
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while True:
        attempt += 1
        try:
            headers = {
                "Content-Type": "application/json",
                **build_auth_headers("POST", url, body, api_key=api_key, hmac_secret=hmac_secret),
            }
            response = session.post(url, data=body, headers=headers, timeout=timeout)
            if response.status_code >= 400 and should_retry_status(response.status_code) and attempt <= max_retries + 1:
                raise requests.HTTPError(f"{response.status_code} retryable response", response=response)

            response.raise_for_status()
            return response.json(), attempt
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            status_code = exc.response.status_code if isinstance(exc, requests.HTTPError) and exc.response is not None else None
            retryable = status_code is None or should_retry_status(status_code)
            if not retryable or attempt > max_retries:
                raise

            sleep_seconds = retry_backoff * (2 ** (attempt - 1))
            print(
                f"[replay] retry attempt={attempt} next_sleep={sleep_seconds:.2f}s "
                f"reason={exc}",
                file=sys.stderr,
            )
            time.sleep(sleep_seconds)


def main() -> int:
    ingest_url = os.getenv("BACKEND_INGEST_URL", "http://localhost:8000/api/v1/stream/ingest")
    dataset_path = Path(os.getenv("DATASET_PATH", str(DEFAULT_DATASET)))
    row_limit = env_int("ROW_LIMIT", 100)
    start_offset = env_int("START_OFFSET", 0)
    replay_rate = env_float("REPLAY_RATE", 5.0)
    request_timeout = env_float("REQUEST_TIMEOUT_SECONDS", 5.0)
    max_retries = env_int("MAX_RETRIES", 3)
    retry_backoff = env_float("RETRY_BACKOFF_SECONDS", 1.0)
    ingest_api_key = os.getenv("INGEST_API_KEY", "")
    ingest_hmac_secret = os.getenv("INGEST_HMAC_SECRET", "")
    resume_from_checkpoint = env_bool("RESUME_FROM_CHECKPOINT", True)
    checkpoint_path = Path(os.getenv("CHECKPOINT_PATH", str(SCRIPT_DIR / "runtime" / "replay_checkpoint.json")))
    failed_log_path = Path(os.getenv("FAILED_LOG_PATH", str(SCRIPT_DIR / "runtime" / "failed_orders.jsonl")))

    if replay_rate <= 0:
        raise ValueError("REPLAY_RATE must be greater than 0")
    if row_limit <= 0:
        raise ValueError("ROW_LIMIT must be greater than 0")
    if start_offset < 0:
        raise ValueError("START_OFFSET must be greater than or equal to 0")
    if max_retries < 0:
        raise ValueError("MAX_RETRIES must be greater than or equal to 0")
    if retry_backoff < 0:
        raise ValueError("RETRY_BACKOFF_SECONDS must be greater than or equal to 0")
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    checkpoint_row = read_checkpoint(checkpoint_path) if resume_from_checkpoint else None
    if checkpoint_row is not None:
        start_offset = max(start_offset, checkpoint_row + 1)

    sleep_seconds = 1.0 / replay_rate
    attempted = 0
    sent = 0
    failed = 0

    print(f"[replay] dataset={dataset_path}")
    print(f"[replay] ingest_url={ingest_url}")
    print(f"[replay] row_limit={row_limit} start_offset={start_offset} replay_rate={replay_rate} rows/s")
    print(f"[replay] max_retries={max_retries} retry_backoff={retry_backoff}s checkpoint={checkpoint_path}")

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
                    result, attempts = post_order(
                        session=session,
                        url=ingest_url,
                        payload=payload,
                        timeout=request_timeout,
                        max_retries=max_retries,
                        retry_backoff=retry_backoff,
                        api_key=ingest_api_key,
                        hmac_secret=ingest_hmac_secret,
                    )
                    sent += 1
                    write_checkpoint(checkpoint_path, index, order_id)
                    risk_score = result.get("risk_score")
                    is_high_risk = result.get("is_high_risk")
                    print(
                        f"[replay] sent={sent} row={index} order_id={order_id} attempts={attempts} "
                        f"risk_score={risk_score} high_risk={is_high_risk}"
                    )
                except requests.RequestException as exc:
                    failed += 1
                    append_failed_log(failed_log_path, index, order_id, exc, payload)
                    print(f"[replay] failed order_id={order_id} error={exc}", file=sys.stderr)

                time.sleep(sleep_seconds)

    print(f"[replay] finished attempted={attempted} sent={sent} failed={failed}")
    return 0 if sent > 0 and failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
