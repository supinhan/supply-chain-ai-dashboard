from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit


API_KEY_HEADER = "X-SCAI-API-Key"
TIMESTAMP_HEADER = "X-SCAI-Timestamp"
SIGNATURE_HEADER = "X-SCAI-Signature"
SIGNATURE_VERSION = "v1"


class RequestAuthError(ValueError):
    pass


def canonical_path_with_query(url_or_path: str) -> str:
    if not url_or_path:
        return "/"

    parts = urlsplit(url_or_path)
    if parts.scheme or parts.netloc:
        path = parts.path or "/"
        return f"{path}?{parts.query}" if parts.query else path

    return url_or_path


def build_auth_headers(
    method: str,
    path_with_query: str,
    body: bytes | str | None = None,
    *,
    api_key: str = "",
    secret: str = "",
    timestamp: int | float | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if api_key:
        headers[API_KEY_HEADER] = api_key
    if not secret:
        return headers

    timestamp_value = str(int(timestamp if timestamp is not None else time.time()))
    headers[TIMESTAMP_HEADER] = timestamp_value
    headers[SIGNATURE_HEADER] = _signature(method, path_with_query, _body_bytes(body), timestamp_value, secret)
    return headers


def verify_request_auth(
    method: str,
    path_with_query: str,
    body: bytes | str | None,
    headers: Mapping[str, Any],
    *,
    expected_api_key: str = "",
    secret: str = "",
    max_age_seconds: int = 300,
) -> None:
    if not expected_api_key and not secret:
        return

    if expected_api_key:
        provided_api_key = _header(headers, API_KEY_HEADER)
        if not provided_api_key or not hmac.compare_digest(str(provided_api_key), expected_api_key):
            raise RequestAuthError("Invalid API key")

    if not secret:
        return

    timestamp = _header(headers, TIMESTAMP_HEADER)
    provided_signature = _header(headers, SIGNATURE_HEADER)
    if not timestamp or not provided_signature:
        raise RequestAuthError("Missing request signature")

    try:
        timestamp_seconds = int(float(str(timestamp)))
    except ValueError as exc:
        raise RequestAuthError("Invalid signature timestamp") from exc

    if max_age_seconds > 0 and abs(time.time() - timestamp_seconds) > max_age_seconds:
        raise RequestAuthError("Expired request signature")

    expected_signature = _signature(method, path_with_query, _body_bytes(body), str(timestamp), secret)
    if not hmac.compare_digest(str(provided_signature), expected_signature):
        raise RequestAuthError("Invalid request signature")


def _signature(method: str, path_with_query: str, body: bytes, timestamp: str, secret: str) -> str:
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join(
        [
            SIGNATURE_VERSION,
            method.upper(),
            canonical_path_with_query(path_with_query),
            timestamp,
            body_hash,
        ]
    )
    digest = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{SIGNATURE_VERSION}={digest}"


def _body_bytes(body: bytes | str | None) -> bytes:
    if body is None:
        return b""
    if isinstance(body, bytes):
        return body
    return body.encode("utf-8")


def _header(headers: Mapping[str, Any], name: str) -> str | None:
    value = headers.get(name)
    if value is not None:
        return str(value)

    lower_name = name.lower()
    for key, candidate in headers.items():
        if str(key).lower() == lower_name:
            return str(candidate)
    return None
