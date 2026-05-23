"""Memory service — Redis short-term (2h TTL).

Short-term: full conversation history in Redis, expires after 2h.
Long-term: written only via the write_memory agent tool (explicit, audited).
"""

import uuid

import structlog

from app.infra import redis

logger = structlog.get_logger()

_TTL = 7200  # 2h — focused triage session; short enough for widget sessions to expire cleanly


def _key(user_id: uuid.UUID, conversation_id: str) -> str:
    return f"conv:{user_id}:{conversation_id}"


async def load_history(user_id: uuid.UUID, conversation_id: str) -> list[dict]:
    """Return stored conversation messages (OpenAI format, no system message)."""
    return await redis.get_json(_key(user_id, conversation_id)) or []


async def save_history(
    user_id: uuid.UUID, conversation_id: str, messages: list[dict]
) -> None:
    """Overwrite history in Redis, refreshing the 2h TTL."""
    await redis.set_json(_key(user_id, conversation_id), messages, ttl=_TTL)
