from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.rag import service as rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


class AskRequest(BaseModel):
    query: str
    alpha: float = Field(default=0.6, ge=0.0, le=1.0)


class AskResponse(BaseModel):
    query: str
    answer: str
    contexts: list[str] = []


@router.post("/ask", response_model=AskResponse)
async def ask(
    req: AskRequest,
    session: AsyncSession = Depends(get_session),
) -> AskResponse:
    if not req.query.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")
    answer, contexts = await rag_service.answer(req.query, session, alpha=req.alpha)
    return AskResponse(query=req.query, answer=answer, contexts=contexts)
