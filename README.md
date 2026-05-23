# Maintainer's Co-Pilot

An AI assistant that helps open-source maintainers triage the inbound issue firehose.
Built on `home-assistant/core` and `home-assistant/home-assistant.io` closed issues.

## What it does

- **Classifies** issues as bug / feature / docs / question (fine-tuned DistilBERT)
- **Extracts** technical entities: function names, file paths, error codes (NER)
- **Summarises** long comment threads
- **Answers** questions via RAG over project docs and past resolved issues
- **Remembers** context across conversations (episodic memory via pgvector)
- **Embeds** as a chat widget on any docs site with CSP-enforced origin control

## Services

| Service | Port | Role |
|---|---|---|
| `api` | 8000 | FastAPI backend — auth, chat, memory, RAG, widget config |
| `model-server` | 8001 | Inference service — classify, NER, summarise |
| `chatbot` | 8501 | Streamlit UI — login, chat, memory inspector, admin |
| `widget` | 3000 | nginx serving built React widget bundle |
| `host` | 8080 | nginx demo host — allowed.html + unallowed.html |
| `db` | 5432 | Postgres 16 + pgvector |
| `redis` | 6379 | Short-term memory + cache |
| `minio` | 9000 | Blob store — model weights, eval reports |
| `vault` | 8200 | HashiCorp Vault dev mode — all secrets |

## Quick start

```bash
# 1. Copy and fill in .env
cp .env.example .env          # set DB_PASSWORD and MINIO_ROOT_PASSWORD

# 2. Start infra
docker compose up -d db redis minio vault

# 3. Seed Vault with all secrets (edit seed.sh with real API keys first)
bash seed.sh

# 4. Run migrations
docker compose up migrate

# 5. Start everything
docker compose up -d
```

The API is live at http://localhost:8000/docs once healthy.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/unit tests/integration

# Lint
ruff check .

# Fetch and index RAG corpus (one-time, requires Vault running)
python -m app.rag.data.fetch_corpus
python -m app.rag.data.index_corpus
```

## Documentation

| File | Contents |
|---|---|
| [docs/DECISIONS.md](docs/DECISIONS.md) | All 12 architectural and model decisions, each backed by a measured metric |
| [docs/ARCH.md](docs/ARCH.md) | Layer diagram, service map, data flow through the stack |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Full local setup, Vault seeding, corpus fetch, eval runs |
| [docs/EVALS.md](docs/EVALS.md) | Evaluation methodology, golden sets, thresholds, how to run |
| [docs/SECURITY.md](docs/SECURITY.md) | Secrets management, CSP enforcement, redaction layer, JWT auth |


## Project 7
### Tag: v0.1.0-week7

-**Dataset**: home-assistant/core + home-assistant.io issues, 1862 train / 399 val / 401 test
-**Classification:** Classical: F1=0.5382 | Fine-tuned: F1=0.6312 | LLM: F1=0.5863
-**Deployment choice:** DistilBERT fine-tuned - best macro-F1 at zero per-request inference cost
-**Embedding model:** BAAI/bge-base-en-v1.5 - asymmetric search query prefix + strong MTEB retrieval scores, Hit@5=0.88 on HA golden set
-**RAG:** hit@5=0.88 | MRR=0.88 | Faithfulness=0.7519 | Answer relevancy=0.6148
-**Long-term memory type:** episodic - stores past turns per user in pgvector; enables cross-conversation recall with no extra infrastructure beyond the RAG vector store
-**Tracing backend:** Langfuse - self-hostable, LLM-native, free tier with strong Python SDK
-**Widget bundle size:** 47 KB (gzipped)
-**LLM:** OpenAI gpt-4o-mini (primary) / Claude Haiku (fallback)