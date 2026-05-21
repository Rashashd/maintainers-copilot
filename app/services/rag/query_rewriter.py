import json
import re
from pathlib import Path

import structlog

from app.infra.llm import get_llm_client
from app.infra.tracing import observe

logger = structlog.get_logger()

_PROMPTS = Path(__file__).parent / "prompts"

_hyde_system = (_PROMPTS / "hyde_query.txt").read_text()
_self_query_system = (_PROMPTS / "self_query.txt").read_text()

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


@observe(name="rag.hyde_rewrite")
async def rewrite_hyde(query: str) -> str:
    """Generate a hypothetical resolved GitHub issue for the query (HyDE)."""
    client = get_llm_client()
    try:
        resp = await client.chat(
            messages=[
                {"role": "system", "content": _hyde_system},
                {"role": "user", "content": query},
            ],
            max_tokens=300,
        )
        text = (resp.content or "").strip()
        if text:
            return text
    except Exception as exc:
        logger.warning("hyde_rewrite_failed", error=str(exc))
    return query


@observe(name="rag.extract_filters")
async def extract_filters(query: str) -> dict:
    """Extract metadata filters from the query via self-querying."""
    client = get_llm_client()
    try:
        resp = await client.chat(
            messages=[
                {"role": "system", "content": _self_query_system},
                {"role": "user", "content": query},
            ],
            max_tokens=100,
        )
        raw = (resp.content or "").strip()
        # strip code fences if model wraps the JSON
        m = _JSON_FENCE.search(raw)
        if m:
            raw = m.group(1).strip()
        filters = json.loads(raw)
        # keep only non-null values
        return {k: v for k, v in filters.items() if v is not None}
    except Exception as exc:
        logger.warning("self_query_failed", error=str(exc))
        return {}
