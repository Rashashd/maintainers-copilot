"""HTTP client for the model-server inference service.

Wraps /classify, /ner, and /summarize endpoints. All methods are async and raise
ToolFailure on non-2xx responses so the agent loop can handle them gracefully.

Usage:
    from app.infra.inference import get_inference_client
    client = get_inference_client()
    result = await client.classify(title="...", body="...")
"""

from dataclasses import dataclass, field

import httpx
import structlog

from app.core.config import get_settings
from app.schemas.errors import ToolFailure

logger = structlog.get_logger()

_client: "InferenceClient | None" = None


# ── Response types ────────────────────────────────────────────────────────────

@dataclass
class ClassifyResult:
    label: str
    scores: dict[str, float]


@dataclass
class Entity:
    text: str
    label: str
    score: float
    start: int
    end: int


@dataclass
class NERResult:
    entities: list[Entity] = field(default_factory=list)


@dataclass
class SummarizeResult:
    summary: str


# ── Client ────────────────────────────────────────────────────────────────────

class InferenceClient:
    def __init__(self, base_url: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(30.0, connect=5.0),
        )

    async def classify(self, title: str, body: str = "") -> ClassifyResult:
        try:
            resp = await self._http.post("/classify", json={"title": title, "body": body})
            resp.raise_for_status()
            data = resp.json()
            return ClassifyResult(label=data["label"], scores=data["scores"])
        except httpx.HTTPStatusError as exc:
            raise ToolFailure("classify", f"HTTP {exc.response.status_code}: {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise ToolFailure("classify", f"Connection error: {exc}") from exc

    async def ner(self, text: str) -> NERResult:
        try:
            resp = await self._http.post("/ner", json={"text": text})
            if resp.status_code == 503:
                # NER model not loaded — non-fatal, return empty
                logger.warning("ner_unavailable")
                return NERResult()
            resp.raise_for_status()
            data = resp.json()
            return NERResult(entities=[Entity(**e) for e in data["entities"]])
        except httpx.HTTPStatusError as exc:
            raise ToolFailure("ner", f"HTTP {exc.response.status_code}: {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise ToolFailure("ner", f"Connection error: {exc}") from exc

    async def summarize(self, text: str, max_sentences: int = 3) -> SummarizeResult:
        try:
            resp = await self._http.post(
                "/summarize",
                json={"text": text, "max_sentences": max_sentences},
            )
            resp.raise_for_status()
            data = resp.json()
            return SummarizeResult(summary=data["summary"])
        except httpx.HTTPStatusError as exc:
            raise ToolFailure("summarize", f"HTTP {exc.response.status_code}: {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise ToolFailure("summarize", f"Connection error: {exc}") from exc

    async def aclose(self) -> None:
        await self._http.aclose()


# ── Module-level singleton ────────────────────────────────────────────────────

def init_inference_client() -> InferenceClient:
    global _client
    settings = get_settings()
    _client = InferenceClient(base_url=settings.inference_url)
    logger.info("inference_client_created", url=settings.inference_url)
    return _client


def get_inference_client() -> InferenceClient:
    if _client is None:
        raise RuntimeError("Inference client not initialised — call init_inference_client() in lifespan first.")
    return _client
