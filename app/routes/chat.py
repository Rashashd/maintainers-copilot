import uuid

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import loop as agent_loop
from app.db.models import User
from app.db.session import get_session
from app.services import memory as memory_service
from app.services.auth import current_active_user

logger = structlog.get_logger()

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    conversation_id = req.conversation_id or str(uuid.uuid4())

    history = await memory_service.load_history(user.id, conversation_id)
    history.append({"role": "user", "content": req.message})

    logger.info(
        "chat_request",
        user_id=str(user.id),
        conversation_id=conversation_id,
        history_len=len(history),
    )

    reply = await agent_loop.run(
        messages=history,
        user_id=user.id,
        conversation_id=conversation_id,
        session=session,
    )

    history.append({"role": "assistant", "content": reply})
    await memory_service.save_history(user.id, conversation_id, history)
    await memory_service.persist_turns(
        user.id, conversation_id, req.message, reply, session
    )

    return ChatResponse(reply=reply, conversation_id=conversation_id)
