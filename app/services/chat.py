import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import loop as agent_loop
from app.infra import embeddings as embedder
from app.repositories import memory as memory_repo
from app.services import memory as memory_service

logger = structlog.get_logger()

_RECALL_LIMIT = 5


async def handle(
    message: str,
    conversation_id: str | None,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> tuple[str, str, list[str]]:
    """Run one chat turn: load history, inject past memories, call agent, persist."""
    conversation_id = conversation_id or str(uuid.uuid4())

    history = await memory_service.load_history(user_id, conversation_id)

    # Inject cross-conversation recall: find past turns semantically similar to this message
    query_vec = await embedder.embed_query(message)
    past = await memory_repo.search_similar(
        session,
        user_id=user_id,
        embedding=query_vec,
        current_conversation_id=conversation_id,
        limit=_RECALL_LIMIT,
    )
    if past:
        recall_text = "\n".join(f"[{e.role}] {e.content}" for e in past)
        history = [
            {
                "role": "user",
                "content": f"Recalled from past conversations:\n{recall_text}",
            },
            {
                "role": "assistant",
                "content": "I have noted the context from our previous conversations.",
            },
        ] + history

    history.append({"role": "user", "content": message})

    logger.info(
        "chat_request",
        user_id=str(user_id),
        conversation_id=conversation_id,
        history_len=len(history),
        recalled=len(past),
    )

    reply, tools_used = await agent_loop.run(
        messages=history,
        user_id=user_id,
        conversation_id=conversation_id,
        session=session,
    )

    history.append({"role": "assistant", "content": reply})
    await memory_service.save_history(user_id, conversation_id, history)

    return reply, conversation_id, tools_used
