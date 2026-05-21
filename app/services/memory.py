"""Memory service — Redis short-term (24h) + pgvector long-term episodic.

Short-term: full conversation history kept in Redis for fast retrieval.
Long-term: individual turns written to MemoryEntry for semantic search.
"""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEntry
from app.infra import embeddings as embedder
from app.infra import redis
from app.repositories import memory as memory_repo

logger = structlog.get_logger()

_TTL = 86400  # 24h


def _key(user_id: uuid.UUID, conversation_id: str) -> str:
    return f"conv:{user_id}:{conversation_id}"


async def load_history(user_id: uuid.UUID, conversation_id: str) -> list[dict]:
    """Return stored conversation messages (OpenAI format, no system message)."""
    return await redis.get_json(_key(user_id, conversation_id)) or []


async def save_history(
    user_id: uuid.UUID, conversation_id: str, messages: list[dict]
) -> None:
    """Overwrite history in Redis, refreshing the 24h TTL."""
    await redis.set_json(_key(user_id, conversation_id), messages, ttl=_TTL)


async def persist_turns(
    user_id: uuid.UUID,
    conversation_id: str,
    user_message: str,
    assistant_reply: str,
    session: AsyncSession,
) -> None:
    """Write user + assistant turns to pgvector for long-term semantic recall."""
    texts = [user_message, assistant_reply]
    vectors = await embedder.embed_texts(texts)

    entries = [
        MemoryEntry(
            user_id=user_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            embedding=vectors[i] if vectors and i < len(vectors) else None,
        )
        for i, (role, content) in enumerate(
            [("user", user_message), ("assistant", assistant_reply)]
        )
    ]

    await memory_repo.insert(session, entries)
    await session.commit()
    logger.info(
        "memory_persisted",
        user_id=str(user_id),
        conversation_id=conversation_id,
    )
