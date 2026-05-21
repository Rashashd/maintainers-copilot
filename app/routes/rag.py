from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_session
from app.schemas.rag import AskRequest, AskResponse
from app.services import rag as rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/ask", response_model=AskResponse)
async def ask(
    req: AskRequest,
    session: AsyncSession = Depends(get_session),
) -> AskResponse:
    if not req.query.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")
    answer, contexts = await rag_service.answer(req.query, session, alpha=req.alpha)
    return AskResponse(query=req.query, answer=answer, contexts=contexts)
