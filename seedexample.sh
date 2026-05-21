#!/usr/bin/env bash
# seed.sh — writes placeholder secrets to Vault dev-mode on first boot.
# Run AFTER `docker compose up vault -d` and BEFORE starting the rest of the stack.
# Usage:  ./seed.sh
# Reads VAULT_ADDR and VAULT_TOKEN from .env (defaults: http://localhost:8200 / dev-root-token)

set -euo pipefail

# Load .env from the same directory as this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  # strip Windows carriage returns before sourcing
  eval "$(grep -v '^#' "$SCRIPT_DIR/.env" | tr -d '\r' | grep -v '^$')"
  set +a
fi

VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-dev-root-token}"


vault_put() {
  local path="$1"
  local payload="$2"
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    --header "X-Vault-Token: $VAULT_TOKEN" \
    --request POST \
    --data "$payload" \
    "$VAULT_ADDR/v1/secret/data/$path")
  if [ "$status" != "200" ] && [ "$status" != "204" ]; then
    echo "ERROR: Vault write to '$path' returned HTTP $status" >&2
    exit 1
  fi
  echo "  ✓ secret/$path"
}

echo "Waiting for Vault to be ready..."
until curl -sf "$VAULT_ADDR/v1/sys/health" > /dev/null; do sleep 1; done
echo "Vault is up. Seeding secrets..."

# Database
vault_put "db" "{\"data\":{\"password\":\"$DB_PASSWORD\"}}"

# MinIO
vault_put "minio" "{\"data\":{\"access_key\":\"minioadmin\",\"secret_key\":\"$MINIO_ROOT_PASSWORD\"}}"

# JWT signing key — replace with a strong random value in staging/production
vault_put "jwt" '{"data":{"signing_key":"changeme"}}'

# LLM keys
vault_put "llm" '{"data":{"openai_api_key":"","anthropic_api_key":""}}'

# Langfuse tracing
vault_put "langfuse" '{"data":{"public_key":"","secret_key":"","host":"https://cloud.langfuse.com"}}'

# GitHub token
vault_put "github" '{"data":{"token":""}}'

echo ""
echo "Done. All secrets written to Vault."
echo "Fill in real values for 'llm', 'langfuse', and 'github' via:"
echo "  vault kv put secret/llm llm_api_key=<key>"