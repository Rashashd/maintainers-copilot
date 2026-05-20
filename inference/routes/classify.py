from fastapi import APIRouter
from pydantic import BaseModel

from inference.runners import classifier

router = APIRouter(tags=["classify"])


class ClassifyRequest(BaseModel):
    title: str
    body: str = ""


class ClassifyResponse(BaseModel):
    label: str
    scores: dict[str, float]


@router.post("/classify", response_model=ClassifyResponse)
async def classify_issue(req: ClassifyRequest) -> ClassifyResponse:
    result = await classifier.classify(req.title, req.body)
    return ClassifyResponse(**result)
