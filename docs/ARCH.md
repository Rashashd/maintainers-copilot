# Architecture

## Layer diagram

```
┌─────────────────────────────────────────────────────────┐
│  Frontends                                               │
│  ┌──────────────────┐   ┌──────────────────────────┐    │
│  │ Streamlit chatbot│   │ React widget (iframe)    │    │
│  │ port 8501        │   │ port 3000                │    │
│  └────────┬─────────┘   └──────────┬───────────────┘    │
└───────────┼─────────────────────────┼───────────────────┘
            │  HTTP                   │  HTTP
┌───────────▼─────────────────────────▼───────────────────┐
│  FastAPI API  (port 8000)                                │
│  routes/ → services/ → repositories/ → db/models        │
│                      → infra/ (vault, llm, redis, minio) │
└───────────┬──────────────────────────────────────────────┘
            │ HTTP
┌───────────▼────────────┐
│  Inference service      │
│  model-server:8001      │
│  classify / NER / sum   │
└─────────────────────────┘
```

## Layer responsibilities

| Layer | Location | Rule |
|---|---|---|
| Routes | `app/routes/` | HTTP only — validate input, call one service, return response |
| Services | `app/services/` | Business logic — no SQL, no HTTP errors |
| Repositories | `app/repositories/` | SQL only — no business logic, never commit |
| Infra | `app/infra/` | External clients — Vault, Redis, MinIO, LLM, embeddings |
| Domain | `app/db/models.py` | ORM models only — no methods |

The rule is strict: routes never touch the database directly, repositories never
raise HTTP exceptions, services never import from routes.

## Request lifecycle — POST /chat

```
1. request_id_middleware     assigns X-Request-ID, binds to structlog context
2. current_active_user       verifies JWT, loads User from DB
3. routes/chat.py            validates ChatRequest schema
4. services/chat.py          load_history (Redis) → agent_loop.run() → save_history
5. agent/loop.py             calls LLM with tools; dispatches via tools/registry.py
6. tools/classify.py         POST /classify to model-server → bug/feature/docs/question
7. tools/rag.py              HyDE rewrite → BM25+dense retrieval → reranker → LLM answer
8. tools/write_memory.py     persists turn to pgvector + writes audit log
9. routes/chat.py            returns ChatResponse
```

## Secrets flow

```
.env  (gitignored — bootstrap only, never read by the api process)
  DB_PASSWORD ──────────────► postgres container init
  MINIO_ROOT_PASSWORD ──────► MinIO container init

seed.sh  (gitignored — run once after Vault starts)
  writes to Vault:
    db/password
    minio/access_key + secret_key
    jwt/signing_key
    llm/openai_api_key + anthropic_api_key
    langfuse/public_key + secret_key + host
    github/token

API lifespan startup:
  vault.load_all()  ──► module-level secret cache (_secrets dict)
  init_db()         ──► SQLAlchemy engine built with vault.get_db_password()
  init_minio()      ──► MinIO client with vault credentials
  init_llm_client() ──► OpenAI / Anthropic client with vault keys
  init_tracing()    ──► Langfuse with vault keys
```

The api container receives zero secrets from environment variables.
If Vault is unreachable at startup the app refuses to boot.

## RAG pipeline

```
user question
      │
      ▼
query_rewriter.py    HyDE: LLM generates a hypothetical resolved GitHub issue
      │              embedding space is now closer to real resolutions
      ▼
retriever.py         BM25 sparse + BGE-base-en-v1.5 dense, RRF fusion (alpha=0.6)
      │              fetches top-20 candidates from pgvector + full-text search
      ▼
reranker.py          cross-encoder/ms-marco-MiniLM-L-6-v2 scores all 20
      │              returns top-5 most relevant chunks
      ▼
services/rag.py      builds prompt from chunks → LLM generates grounded answer
```

## Agent tool loop

The agent (Claude / GPT-4o-mini) has five tools it can call in sequence:

| Tool | What it does |
|---|---|
| `classify` | Labels issue as bug / feature / docs / question via model-server |
| `extract_entities` | Pulls function names, file paths, error codes via NER |
| `summarize_issue` | Condenses long comment threads |
| `search_knowledge_base` | Full RAG pipeline — returns answer + source chunks |
| `write_memory` | Persists a key fact to pgvector long-term memory |

Every classify / NER / summarise call is logged to `inference_logs` for drift monitoring.

## Widget CSP enforcement

```
allowed.html  (demo docs site, served by host:8080)
  └── <script> injects <iframe src="widget:3000/index.html?id=...">

React widget on load:
  GET /widget/config/{id}  →  API returns config + header:
    Content-Security-Policy: frame-ancestors https://allowed-origin.com

Browser checks: is the parent page in frame-ancestors?
  ✓ allowed.html   → widget loads
  ✗ unallowed.html → browser blocks with CSP error
```

## Database schema

| Table | Purpose |
|---|---|
| `user` | fastapi-users managed; adds `role` (user / admin) |
| `widgets` | Widget config: name, allowed_origins, theme, greeting, enabled_tools |
| `memory_entries` | Episodic long-term memory; 768-dim pgvector embedding per turn |
| `documents` | RAG corpus chunks; 768-dim pgvector embedding + BM25 tsvector |
| `audit_logs` | Immutable log: role_change, memory_write, deletion, widget_update |
| `inference_logs` | Every classify / NER / summarise call with input + output |
