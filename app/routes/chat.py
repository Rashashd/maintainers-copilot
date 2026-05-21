from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_active_user, get_session
from app.db.models import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat as chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    reply, conversation_id = await chat_service.handle(
        message=req.message,
        conversation_id=req.conversation_id,
        user_id=user.id,
        session=session,
    )
    return ChatResponse(reply=reply, conversation_id=conversation_id)
