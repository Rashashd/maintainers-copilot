from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.startup_checks import run_startup_checks
from app.db.session import init_db
from app.infra import vault
from app.infra.embeddings import init_embedder
from app.infra.inference import init_inference_client
from app.infra.llm import init_llm_client
from app.infra.minio import init_minio
from app.infra.redis import init_redis
from app.infra.tracing import init_tracing
from app.rag.reranker import init_reranker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Configure structured logging first so all subsequent logs are formatted
    configure_logging(debug=False)

    # 2. Load all secrets from Vault into the module-level cache
    await vault.load_all()

    # 3. Init database engine with password from Vault (no password in env)
    s = get_settings()
    init_db(
        f"postgresql+asyncpg://{s.db_user}:{vault.get_db_password()}"
        f"@{s.db_host}:{s.db_port}/{s.db_name}"
    )

    # 4. Init tracing with Vault-loaded keys
    pub, sec, host = vault.get_langfuse_keys()
    if pub and sec:
        init_tracing(public_key=pub, secret_key=sec, host=host)

    # 5. Init LLM client (OpenAI primary, Anthropic fallback)
    init_llm_client(
        openai_key=vault.get_openai_api_key(),
        anthropic_key=vault.get_anthropic_api_key(),
    )

    # 6. Load embedding and reranking models into memory
    init_embedder()
    init_reranker()

    # 7. Init infrastructure clients
    init_redis()
    init_minio()
    init_inference_client()

    # 8. Run refuse-to-boot checks
    await run_startup_checks()

    yield
