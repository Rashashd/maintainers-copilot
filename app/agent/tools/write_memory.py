"""write_memory tool — persists episodic memory to pgvector."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEntry
from app.infra import embeddings as embedder
from app.infra.redact import redact
from app.infra.tracing import observe
from app.repositories import audit as audit_repo
from app.repositories import memory as memory_repo

logger = structlog.get_logger()


@observe(name="agent.tool.write_memory")
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
    await memory_repo.insert(session, [entry])
    await audit_repo.log(
        session,
        actor_id=user_id,
        action="memory_write",
        target={"type": "memory_entry", "id": str(entry.id), "conversation_id": conversation_id},
    )
    await session.commit()

    logger.info("memory_written", user_id=str(user_id), conversation_id=conversation_id)
    return f"Remembered: {content[:120]}"
