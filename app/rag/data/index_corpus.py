"""
Run the RAG corpus indexer from the command line.

Usage:
    python -m app.rag.data.index_corpus
    python -m app.rag.data.index_corpus --parquet path/to/rag_corpus.parquet
"""
import argparse
import asyncio
import sys
from pathlib import Path

# ensure project root is on sys.path when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.config import get_settings
from app.db import session as _db_session
from app.db.session import init_db
from app.infra import vault
from app.infra.embeddings import init_embedder
from app.rag.indexer import index_corpus

_DEFAULT_PARQUET = Path(__file__).parent / "rag_corpus.parquet"


async def main(parquet_path: Path) -> None:
    if not parquet_path.exists():
        print(f"ERROR: parquet file not found: {parquet_path}")
        sys.exit(1)

    await vault.load_all()
    s = get_settings()
    init_db(
        f"postgresql+asyncpg://{s.db_user}:{vault.get_db_password()}"
        f"@{s.db_host}:{s.db_port}/{s.db_name}"
    )

    print("Loading embedding model...")
    init_embedder()

    assert _db_session.async_session_factory is not None
    async with _db_session.async_session_factory() as session:
        print(f"Indexing corpus from: {parquet_path}")
        n = await index_corpus(str(parquet_path), session)
        print(f"Done — {n:,} chunks written to documents table.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--parquet",
        default=str(_DEFAULT_PARQUET),
        help="Path to the RAG corpus parquet file",
    )
    args = parser.parse_args()
    asyncio.run(main(Path(args.parquet)))
