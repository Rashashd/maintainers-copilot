# Runbook

## Prerequisites

- Docker Desktop running
- Python 3.12
- `uv` or `pip` for Python package management

## First-time setup

### 1. Create your .env

```bash
cp .env.example .env
```

Edit `.env` and set real values for:
- `DB_PASSWORD` — Postgres password (used only by docker-compose to init the DB)
- `MINIO_ROOT_PASSWORD` — MinIO admin password (used only by docker-compose)
- `VAULT_TOKEN` — leave as `dev-root-token` for local dev

### 2. Create seed.sh

`seed.sh` is gitignored. Use `seedexample.sh` as a starting point:

```bash
cp seedexample.sh seed.sh
```

Open `seed.sh` and fill in real values for:
- `openai_api_key` / `anthropic_api_key` — at least one LLM key
- `github/token` — for fetching the RAG corpus from the GitHub API

The DB password and MinIO password are read automatically from `.env` — no need
to hardcode them in `seed.sh`.

`seed.sh` reads `VAULT_ADDR` and `VAULT_TOKEN` from `.env` and defaults to
`http://localhost:8200` / `dev-root-token` if not set.

### 3. Start infra

```bash
docker compose up -d db redis minio vault
```

Wait for all four to be healthy:
```bash
docker compose ps
```

### 4. Seed Vault

```bash
bash seed.sh
```

This writes all secrets into Vault's KV store. The api container reads from here at startup — it never reads `.env` directly.

### 5. Run migrations

```bash
docker compose up migrate
```

Creates all tables including pgvector extension, widgets, memory_entries, documents, audit_logs, inference_logs.

### 6. Start all services

```bash
docker compose up -d
```

Services become available at:
- API + docs: http://localhost:8000/docs
- Streamlit chatbot: http://localhost:8501
- Demo host: http://localhost:8080
- Vault UI: http://localhost:8200 (token: dev-root-token)
- MinIO console: http://localhost:9001 (credentials from seed.sh)

## Fetch and index the RAG corpus

This is a one-time step. Requires Vault to be running and seeded (for the GitHub token).

```bash
# Fetch ~4000 resolved issues from home-assistant/core and home-assistant/home-assistant.io
python -m app.rag.data.fetch_corpus

# Chunk and embed them into the documents table (~30-60 min depending on hardware)
python -m app.rag.data.index_corpus
```

## Run evals locally

### Classification eval

```bash
python -m eval.classification.runner
```

Runs on `eval/classification/golden_set.jsonl` (25 items). Checks against thresholds in `eval_thresholds.yaml`. Exits non-zero if any threshold is breached.

### RAG eval

Requires the API to be running and the corpus to be indexed.

```bash
python -m eval.rag.runner --api-url http://localhost:8000
```

Runs on `eval/rag/golden_set.jsonl` (25 items). Produces `eval/rag/eval_report.json`.

To skip the RAGAS LLM-as-judge step (faster, no API cost):
```bash
python -m eval.rag.runner --api-url http://localhost:8000 --no-ragas
```

## Rebuild after code changes

```bash
# Rebuild only the services whose code changed
docker compose build api
docker compose up -d --no-deps api
```

## Useful commands

```bash
# Stream logs from the api
docker compose logs -f api

# Check Vault secrets
docker exec maintainers-copilot-vault-1 vault kv get -address=http://127.0.0.1:8200 secret/db

# Open a psql shell
docker exec -it maintainers-copilot-db-1 psql -U dbadmin -d copilot

# Run unit + integration tests
pytest tests/unit tests/integration -v

# Lint
ruff check .
```

## Stopping

```bash
docker compose down          # stop containers, keep volumes
docker compose down -v       # stop containers AND delete all data
```
