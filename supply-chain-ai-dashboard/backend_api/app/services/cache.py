from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from ..core.config import Settings, settings


class CacheClient:
    def __init__(self, config: Settings = settings) -> None:
        self.config = config
        self.client: redis.Redis | None = None
        self.enabled = False

    async def connect(self) -> None:
        try:
            self.client = redis.from_url(self.config.redis_url, decode_responses=True)
            await self.client.ping()
            self.enabled = True
        except Exception:
            self.client = None
            self.enabled = False

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()

    async def set_kpi(self, payload: dict[str, Any]) -> None:
        if self.client is None:
            return
        await self.client.set("kpi:realtime:dashboard", json.dumps(payload, ensure_ascii=False))

    async def publish_alert(self, payload: dict[str, Any]) -> None:
        if self.client is None:
            return
        await self.client.publish("alerts:channel", json.dumps(payload, ensure_ascii=False))


cache_client = CacheClient()
