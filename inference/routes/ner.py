from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from inference.runners import ner as ner_runner

router = APIRouter(tags=["ner"])


class NERRequest(BaseModel):
    text: str


class Entity(BaseModel):
    text: str
    label: str
    score: float
    start: int
    end: int


class NERResponse(BaseModel):
    entities: list[Entity]


@router.post("/ner", response_model=NERResponse)
async def extract_entities(req: NERRequest) -> NERResponse:
    try:
        entities = await ner_runner.extract_entities(req.text)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return NERResponse(entities=[Entity(**e) for e in entities])
