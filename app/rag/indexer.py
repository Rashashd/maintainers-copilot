import structlog
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra import embeddings as embedder
from app.rag import chunker
from app.repositories import documents as doc_repo

logger = structlog.get_logger()

_EMBED_BATCH = 512


async def index_corpus(parquet_path: str, session: AsyncSession) -> int:
    """
    Resumable indexer: skips issues already in the documents table and commits
    after every _EMBED_BATCH chunks so progress is saved incrementally.

    Returns the number of new chunks written in this run.
    """
    df = pd.read_parquet(parquet_path)
    logger.info("indexer_loaded_corpus", rows=len(df), path=parquet_path)

    # ── skip already-indexed issues ───────────────────────────────────────────
    all_source_ids = [row.get("url") or str(row.get("number", "")) for _, row in df.iterrows()]
    already_indexed = await doc_repo.fetch_indexed_source_ids(session, all_source_ids)
    logger.info("indexer_resume_check", already_indexed=len(already_indexed), remaining=len(df) - len(already_indexed))

    # ── chunk ─────────────────────────────────────────────────────────────────
    all_chunks: list[dict] = []
    for _, row in df.iterrows():
        source_id = row.get("url") or str(row.get("number", ""))
        if source_id in already_indexed:
            continue
        all_chunks.extend(chunker.chunk_issue(row.to_dict()))

    logger.info("indexer_chunked", new_chunks=len(all_chunks))

    if not all_chunks:
        return 0

    # ── embed in batches ──────────────────────────────────────────────────────
    contents = [c["content"] for c in all_chunks]
    embeddings: list[list[float]] = []
    for i in range(0, len(contents), _EMBED_BATCH):
        vecs = await embedder.embed_texts(contents[i : i + _EMBED_BATCH])
        embeddings.extend(vecs)
        logger.info("indexer_embedding_progress", done=i + len(vecs), total=len(contents))

    for chunk, vec in zip(all_chunks, embeddings):
        chunk["embedding"] = vec

    # ── single commit at the end ──────────────────────────────────────────────
    await doc_repo.insert_chunks(session, all_chunks)
    await session.commit()

    logger.info("indexer_done", chunks_written=len(all_chunks))
    return len(all_chunks)
