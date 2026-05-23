from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str
    alpha: float = Field(default=0.6, ge=0.0, le=1.0)
    use_reranker: bool = True
    use_hyde: bool = True


class AskResponse(BaseModel):
    query: str
    answer: str
    contexts: list[str] = []
