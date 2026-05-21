"""Infrastructure topology config only — no secrets.

All secrets (DB password, API keys, JWT key, etc.) are loaded from Vault
at startup via app.infra.vault.load_all() and accessed via the typed getters
in that module. Nothing secret belongs here.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Full URL injected by docker-compose (includes DB_PASSWORD from .env).
    # The app uses this URL only to connect; the password also lives in Vault
    # (written by seed.sh) so the app never reads DB_PASSWORD from env directly.
    database_url: str = "postgresql+asyncpg://dbadmin:changeme@localhost:5432/copilot"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Vault — connection info only, not a secret
    vault_addr: str = "http://localhost:8200"
    vault_token: str = "dev-root-token"  # read from VAULT_TOKEN env var in compose

    # MinIO — endpoint only; credentials come from Vault
    minio_endpoint: str = "localhost:9000"
    minio_secure: bool = False
    minio_bucket_weights: str = "model-weights"
    minio_bucket_evals: str = "eval-reports"
    minio_bucket_chunks: str = "retrieved-chunks"

    # Inference service
    inference_url: str = "http://localhost:8001"

    # Eval thresholds file path
    eval_thresholds_path: str = "eval_thresholds.yaml"

    # App
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
