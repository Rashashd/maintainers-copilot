from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document
from app.infra import embeddings as embedder
from app.infra.llm import get_llm_client
from app.infra.tracing import get_client, observe
from app.rag import query_rewriter, retriever
from app.rag.reranker import rerank

logger = structlog.get_logger()

_PROMPTS = Path(__file__).parent.parent / "rag" / "prompts"
_answer_system = (_PROMPTS / "rag_answer.txt").read_text()

_RETRIEVE_K = 50   # candidates from hybrid retrieval
_RERANK_K = 15     # final passages sent to LLM


@observe(name="rag.answer")
async def answer(
    query: str,
    session: AsyncSession,
    alpha: float = 0.6,
) -> tuple[str, list[str]]:
    """
    Full RAG pipeline:
      1. Self-querying  → metadata filters
      2. HyDE           → hypothetical answer, embed as document vector
      3. Hybrid retrieval (dense + FTS, RRF)
      4. Cross-encoder reranking
      5. LLM answer generation
    """
    # Override trace input: expose only the query, not the SQLAlchemy session or alpha
    get_client().update_current_span(input={"query": query, "alpha": alpha})

    # 1. extract metadata filters from the query
    filters = await query_rewriter.extract_filters(query)
    logger.info("rag_filters_extracted", filters=filters)

    # 2. HyDE: generate hypothetical answer and embed it as a document
    hypothesis = await query_rewriter.rewrite_hyde(query)
    query_vector = (await embedder.embed_texts([hypothesis]))[0]

    # 3. hybrid retrieval
    docs = await retriever.retrieve(
        session=session,
        query_vector=query_vector,
        query_text=query,        # raw query text for BM25
        filters=filters,
        top_k=_RETRIEVE_K,
        alpha=alpha,
    )

    if not docs:
        return "I could not find any relevant issues for your question.", []

    # 4. cross-encoder reranking
    passages = [doc.content for doc in docs]
    scores = await rerank(query, passages)
    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    top_docs = [doc for doc, _ in ranked[:_RERANK_K]]

    # 5. build context and generate answer
    context = _build_context(top_docs)
    client = get_llm_client()
    resp = await client.chat(
        messages=[
            {"role": "system", "content": _answer_system},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
        max_tokens=512,
    )

    result = (resp.content or "").strip()
    contexts = [doc.content for doc in top_docs]
    get_client().update_current_span(output={"answer": result})
    return result, contexts


def _build_context(docs: list[Document]) -> str:
    parts = []
    for doc in docs:
        issue_num = (doc.metadata_ or {}).get("issue_number", "")
        header = f"Issue #{issue_num} — {doc.title or ''}" if issue_num else (doc.title or "")
        parts.append(f"[{header}]\n{doc.content}")
    return "\n\n---\n\n".join(parts)
