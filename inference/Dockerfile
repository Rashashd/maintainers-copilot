FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system ".[torch]"

COPY inference/ ./inference/
COPY ml/finetune/output/ ./ml/finetune/output/

ENV MODEL_DIR=ml/finetune/output

EXPOSE 8001

CMD ["uvicorn", "inference.main:app", "--host", "0.0.0.0", "--port", "8001"]
