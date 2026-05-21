from fastapi import APIRouter
from pydantic import BaseModel, Field

from inference.runners import summarizer

router = APIRouter(tags=["summarize"])


class SummarizeRequest(BaseModel):
    text: str
    max_sentences: int = Field(default=3, ge=1, le=10)


class SummarizeResponse(BaseModel):
    summary: str


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_text(req: SummarizeRequest) -> SummarizeResponse:
    summary = await summarizer.summarize(req.text, req.max_sentences)
    return SummarizeResponse(summary=summary)
