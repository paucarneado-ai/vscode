# Brief: Maintenance & Operations

## Purpose
VPS deployment, backup, health checking, incident recovery.

## Current scope
- Deploy: `deploy/deploy-staging.sh` (syncs backend + static site + Caddy config)
- Backup: `deploy/ops/backup-sqlite.sh` (daily cron, 30-file retention)
- Restore: `deploy/ops/restore-sqlite.sh` (interactive, validates integrity, pre-restore snapshot)
- Health check: `deploy/ops/check-staging.sh` (services, endpoints, auth, DB integrity, backup freshness, cron, disk)
- Smoke test: `deploy/ops/smoke-intake.sh` (create + dedup + retrieve + score verify)
- Backup verify: `deploy/ops/verify-backup.sh` (integrity + schema + data readable + count comparison)
- Pre-deploy checks: `scripts/check.sh` (unit tests + E2E smoke + semgrep)
- Rescore: `scripts/rescore_leads.py` (one-off historical rescore)

## Infrastructure
- VPS: Hostinger, 76.13.48.227
- Stack: uvicorn (127.0.0.1:8000) → Caddy (:8080) → Docker proxy nginx → Traefik (:443, EasyPanel SSL)
- Domain: sentyacht.es (Traefik handles SSL)
- DB: SQLite at /home/openclaw/data/leads.db
- Backups: /home/openclaw/backups/

## Key config
- Auth: OPENCLAW_API_KEY in .env, fail-closed in production
- Rate limit: RATE_LIMIT_MAX=10, RATE_LIMIT_WINDOW=60 (public intake only)
- Sentry: SENTRY_DSN (backend + frontend configured)
- OTel: OTEL_ENABLED (code exists, not activated)

## Do not touch
- Caddy restricted surface (only POST /api/leads/intake/web public)
- Docker proxy container (thin nginx, do not add content)
- EasyPanel/Traefik config (managed by EasyPanel, do not edit main.yaml)

## Accepted debt
- No automated alerting (operator checks manually)
- No log rotation policy
- Smoke test creates real test leads (filterable by source=webhook:ops-smoke)
- OTel configured but never enabled

## Likely next block
- Set up backup cron (one-time VPS command, documented in runbook)
- Validate Sentry receives real events

## See also
- Changing deploy process? Also read `deploy/deploy-staging.sh`
- Changing Caddy surface? Also read `docs/briefs/guardrails.md` (approval required)
- Adding monitoring? Read `docs/llm_guardrails.md` section 6 (intentionally unbuilt)
