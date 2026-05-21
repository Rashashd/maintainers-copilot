import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import loop as agent_loop
from app.services import memory as memory_service

logger = structlog.get_logger()


async def handle(
    message: str,
    conversation_id: str | None,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> tuple[str, str]:
    """Run one chat turn: load history, call agent, persist, return (reply, conversation_id)."""
    conversation_id = conversation_id or str(uuid.uuid4())

    history = await memory_service.load_history(user_id, conversation_id)
    history.append({"role": "user", "content": message})

    logger.info(
        "chat_request",
        user_id=str(user_id),
        conversation_id=conversation_id,
        history_len=len(history),
    )

    reply = await agent_loop.run(
        messages=history,
        user_id=user_id,
        conversation_id=conversation_id,
        session=session,
    )

    history.append({"role": "assistant", "content": reply})
    await memory_service.save_history(user_id, conversation_id, history)
    await memory_service.persist_turns(user_id, conversation_id, message, reply, session)

    return reply, conversation_id
