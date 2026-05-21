import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document
from app.infra.tracing import observe
from app.repositories import documents as doc_repo

logger = structlog.get_logger()

_RRF_K = 60


def _rrf_fuse(
    dense_docs: list[Document],
    sparse_docs: list[Document],
    alpha: float,
) -> list[Document]:
    """
    Reciprocal Rank Fusion.

    alpha=0 → pure dense, alpha=1 → pure sparse.
    score(d) = (1-alpha) * 1/(k + rank_dense) + alpha * 1/(k + rank_sparse)
    """
    scores: dict = {}
    doc_map: dict = {}

    for rank, doc in enumerate(dense_docs):
        key = str(doc.id)
        scores[key] = scores.get(key, 0.0) + (1 - alpha) / (_RRF_K + rank + 1)
        doc_map[key] = doc

    for rank, doc in enumerate(sparse_docs):
        key = str(doc.id)
        scores[key] = scores.get(key, 0.0) + alpha / (_RRF_K + rank + 1)
        doc_map[key] = doc

    sorted_keys = sorted(scores, key=lambda k: scores[k], reverse=True)
    return [doc_map[k] for k in sorted_keys]


@observe(name="rag.retrieve")
async def retrieve(
    session: AsyncSession,
    query_vector: list[float],
    query_text: str,
    filters: dict | None = None,
    top_k: int = 50,
    alpha: float = 0.5,
) -> list[Document]:
    """
    Hybrid retrieval: dense (pgvector cosine) + sparse (PostgreSQL FTS), fused via RRF.

    Returns up to top_k documents sorted by combined RRF score.
    alpha is swept on the golden set; 0.5 is the default.
    """
    dense_docs, sparse_docs = await _run_both(
        session, query_vector, query_text, filters, top_k
    )

    fused = _rrf_fuse(dense_docs, sparse_docs, alpha)
    logger.debug(
        "hybrid_retrieve",
        dense=len(dense_docs),
        sparse=len(sparse_docs),
        fused=len(fused),
        alpha=alpha,
    )
    return fused[:top_k]


async def _run_both(
    session: AsyncSession,
    query_vector: list[float],
    query_text: str,
    filters: dict | None,
    limit: int,
) -> tuple[list[Document], list[Document]]:
    # sequential — AsyncSession is not safe for concurrent use
    dense = await doc_repo.vector_search(session, query_vector, limit=limit, filters=filters)
    sparse = await doc_repo.fts_search(session, query_text, limit=limit, filters=filters)
    return dense, sparse
