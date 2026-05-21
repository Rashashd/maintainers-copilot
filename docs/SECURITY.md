# Security

## Secrets management

All application secrets are stored in HashiCorp Vault (dev mode for local,
production mode for deployment). The api container receives zero secrets via
environment variables at runtime.

### What lives where

| Secret | Location | Who reads it |
|---|---|---|
| DB password | Vault `secret/db` | api (via vault.get_db_password()) |
| MinIO credentials | Vault `secret/minio` | api, model-server |
| JWT signing key | Vault `secret/jwt` | api (JWT strategy) |
| OpenAI / Anthropic keys | Vault `secret/llm` | api (LLM client) |
| Langfuse keys | Vault `secret/langfuse` | api (tracing) |
| GitHub token | Vault `secret/github` | fetch_corpus.py (offline script) |
| DB_PASSWORD | `.env` only | docker-compose (postgres init) |
| MINIO_ROOT_PASSWORD | `.env` only | docker-compose (MinIO init) |

`.env` is gitignored. `seed.sh` (also gitignored) writes all secrets into Vault.

### Refuse-to-boot guarantees

The app will not start if any of the following conditions are true:

1. Vault is unreachable
2. Classifier weights are missing from MinIO
3. Classifier weights SHA-256 does not match the expected hash
4. Langfuse tracing backend is misconfigured
5. Any threshold in `eval_thresholds.yaml` is zero, null, or disabled

These checks run in `app/core/startup_checks.py` before the app accepts traffic.

---

## Widget CSP enforcement

The chat widget is embedded via an `<iframe>` on docs sites. Which sites are
allowed to embed it is controlled per-widget via the `allowed_origins` list
stored in the `widgets` database table.

When the React widget calls `GET /widget/config/{id}`, the API sets:

```
Content-Security-Policy: frame-ancestors https://allowed-site.com
```

The browser enforces this header — if the page hosting the iframe is not in
`frame-ancestors`, the browser blocks the iframe with a CSP violation and the
widget never loads. This is enforced client-side by the browser with no
application code needed.

Updating `allowed_origins` requires admin authentication (`PATCH /widget/config/{id}`).

---

## Authentication

All API endpoints except `GET /widget/config/{id}` and `/auth/jwt/login` require
a valid JWT Bearer token.

- Tokens are issued at `/auth/jwt/login` (POST with email + password)
- Signed with a key stored in Vault — never hardcoded
- Lifetime: 24 hours (one triage session)
- Two roles: `user` (chat, memory) and `admin` (user management, audit logs, widget config)
- Role changes are written to the audit log immediately

---

## Redaction layer

All text that flows through logs, traces, or memory is passed through
`app/infra/redact.py` before being written. The following patterns are
scrubbed and replaced with placeholders:

| Pattern | Placeholder |
|---|---|
| OpenAI API key (`sk-...`) | `<OPENAI_KEY>` |
| Anthropic API key (`sk-ant-...`) | `<ANTHROPIC_KEY>` |
| GitHub PAT (`ghp_...`) | `<GITHUB_TOKEN>` |
| JWT token (`eyJ...`) | `<JWT>` |
| Email addresses | `<EMAIL>` |
| Postgres DSN with password | `postgresql://<REDACTED>@` |
| Langfuse key (`pk-lf-...`) | `<LANGFUSE_KEY>` |

Tests for all patterns are in `tests/unit/test_redact.py` and run on every push.

---

## Audit log

Every sensitive action is recorded in the `audit_logs` table:

| Action | Trigger |
|---|---|
| `role_change` | Admin changes a user's role |
| `memory_write` | Agent writes a fact to long-term memory |
| `deletion` | User deletes a memory entry |
| `widget_create` | Admin creates a widget |
| `widget_update` | Admin updates widget config |
| `widget_delete` | Admin deletes a widget |

Audit log entries are never deleted or updated — append-only.
