from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Supply Chain AI Backend")
    api_prefix: str = os.getenv("API_PREFIX", "/api/v1")
    environment: str = os.getenv("ENVIRONMENT", "development")

    database_url: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BACKEND_DIR / 'dev.db'}",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    ai_service_url: str = os.getenv("AI_SERVICE_URL", "").rstrip("/")
    local_model_path: Path = Path(
        os.getenv(
            "LOCAL_RISK_MODEL_PATH",
            PROJECT_ROOT / "ai_algorithms/supplychain-ai-service/model/risk_model.pkl",
        )
    )
    local_encoder_path: Path = Path(
        os.getenv(
            "LOCAL_SHIPPING_ENCODER_PATH",
            PROJECT_ROOT / "ai_algorithms/supplychain-ai-service/model/shipping_mode_encoder.pkl",
        )
    )
    risk_threshold: float = float(os.getenv("RISK_THRESHOLD", "0.85"))
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "3.0"))

    allowed_origins: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        origins = os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost,http://localhost:5173,http://127.0.0.1:5173",
        )
        object.__setattr__(self, "allowed_origins", _split_csv(origins))


settings = Settings()
