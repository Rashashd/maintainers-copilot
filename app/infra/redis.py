"""Async Redis client — short-term memory and cache.

Usage:
    from app.infra.redis import get_redis
    r = get_redis()
    await r.set_json("conv:abc", data, ttl=86400)
"""

import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from app.core.config import get_settings

logger = structlog.get_logger()

_client: aioredis.Redis | None = None


def init_redis() -> aioredis.Redis:
    global _client
    settings = get_settings()
    _client = aioredis.from_url(settings.redis_url, decode_responses=True)
    logger.info("redis_client_created", url=settings.redis_url)
    return _client


def get_redis() -> aioredis.Redis:
    if _client is None:
        raise RuntimeError("Redis not initialised — call init_redis() in lifespan first.")
    return _client


async def ping_redis() -> bool:
    try:
        return await get_redis().ping()
    except Exception as exc:
        logger.warning("redis_ping_failed", error=str(exc))
        return False


# ── Typed helpers ─────────────────────────────────────────────────────────────

async def set_json(key: str, value: Any, ttl: int | None = None) -> None:
    """Serialise value to JSON and store with optional TTL (seconds)."""
    r = get_redis()
    payload = json.dumps(value)
    if ttl:
        await r.setex(key, ttl, payload)
    else:
        await r.set(key, payload)


async def get_json(key: str) -> Any | None:
    """Return deserialised value or None if key missing."""
    raw = await get_redis().get(key)
    return json.loads(raw) if raw is not None else None


async def delete(key: str) -> None:
    await get_redis().delete(key)


async def exists(key: str) -> bool:
    return bool(await get_redis().exists(key))
