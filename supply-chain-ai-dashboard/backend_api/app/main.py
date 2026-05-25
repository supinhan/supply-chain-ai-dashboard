from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router as api_router
from .core.config import settings
from .db.database import init_db
from .services.cache import cache_client
from .services.model_runner import risk_model_runner


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    risk_model_runner.load()
    await cache_client.connect()
    yield
    await cache_client.close()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/health")
async def health_check() -> dict:
    return {
        "status": "ok",
        "environment": settings.environment,
        "model_mode": risk_model_runner.mode,
    }
