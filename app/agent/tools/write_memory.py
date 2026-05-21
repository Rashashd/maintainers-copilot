"""write_memory tool — persists episodic memory to pgvector.

The full memory service (Redis short-term + pgvector long-term) is built in
app/services/memory/. This tool writes directly to MemoryEntry so the agent
loop has no circular dependency on the memory service layer.
"""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEntry
from app.infra import embeddings as embedder
from app.infra.redact import redact

logger = structlog.get_logger()


async def run(args: dict, user_id: uuid.UUID, conversation_id: str, session: AsyncSession) -> str:
    content = redact(args["content"])

    vectors = await embedder.embed_texts([content])
    embedding = vectors[0] if vectors else None

    entry = MemoryEntry(
        user_id=user_id,
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        embedding=embedding,
    )
    session.add(entry)
    await session.commit()

    logger.info("memory_written", user_id=str(user_id), conversation_id=conversation_id)
    return f"Remembered: {content[:120]}"
