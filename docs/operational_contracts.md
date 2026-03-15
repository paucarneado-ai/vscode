# OpenClaw — Operational Contracts & Technical State

> Recovered from the pre-refactor `.claude/CLAUDE.md` (2026-03-14).
> This file preserves concrete operational details that the new governance constitution does not carry.

---

## Current MVP State

- Persistence: SQLite (local file)
- Framework: FastAPI
- Tests: pytest with TestClient

---

## Endpoints Operativos

| Endpoint | Method | Status |
|---|---|---|
| /health | GET | OK |
| /leads | POST | OK — normalizes source/email, dedup by email+source, 409 if duplicate |
| /leads/ingest | POST | OK — bulk ingestion, reuses internal create path, returns created/duplicates/errors counts |
| /leads/webhook/{provider} | POST | OK — single lead via webhook, source set to webhook:{provider}, 409 if duplicate |
| /leads/webhook/{provider}/batch | POST | OK — batch webhook ingestion, same semantics as single webhook |
| /leads/external | POST | OK — canonical external adapter, accepts phone/metadata via @ext: serialization in notes |
| /leads | GET | OK — filters: source, min_score, limit, offset, q (LIKE on name/email/notes) |
| /leads/summary | GET | OK — aggregate stats: total, avg_score, low/medium/high bucket counts. Supports source, min_score, q filters |
| /leads/actionable | GET | OK — list of leads with operational summary (next_action, alert, instruction). Supports source, limit filters |
| /leads/actionable/worklist | GET | OK — actionable leads grouped by next_action, priority-ordered |
| /leads/export.csv | GET | OK — CSV export with same filters as GET /leads |
| /leads/{id} | GET | OK |
| /leads/{id}/pack | GET | OK — JSON with rating and summary |
| /leads/{id}/pack/html | GET | OK — rendered HTML |
| /leads/{id}/pack.txt | GET | OK — plain text |
| /leads/{id}/operational | GET | OK — single lead operational summary (score, rating, next_action, alert, instruction) |
| /leads/{id}/delivery | GET | OK — delivery JSON with embedded pack |
| /internal/queue | GET | OK — flat prioritized queue sorted by alert DESC, action priority ASC, score DESC. Supports source, limit filters. Limit applies after sort |
| /internal/dispatch | GET | OK — automation-ready batch of dispatch payloads with embedded lead packs. Supports source, limit, action filters. Limit applies after sort and filter. Excludes claimed leads |
| /internal/dispatch/claim | POST | OK — claim leads for processing. Validates lead existence. Returns claimed/already_claimed/not_found |

---

## Accepted Contracts

### POST /leads
- Normalizes source (strip + lower) and email (strip + lower) before persisting
- Lightweight deduplication: email + source (post-normalization). Duplicate returns 409 with body LeadCreateResult and meta.status = "duplicate"
- Scoring is calculated with normalized source
- Response 200: LeadCreateResult with meta.status = "accepted"

### GET /leads
- Optional query params: source (exact match), min_score (>= int, ge=0), limit (ge=1), offset (ge=0), q (LIKE %q% on name, email, notes)
- All combinable with AND
- ORDER BY id DESC always
- Offset without limit uses LIMIT -1 (SQLite idiom)
- Invalid params return 422 (FastAPI Query validation)

### GET /internal/dispatch
- Optional query params: source (exact match, normalized), limit (ge=1), action (exact match on next_action, e.g. `send_to_client`)
- Returns `AutomationBatchResponse`: `generated_at`, `total`, `items`
- Each item is `AutomationDispatch`: `lead_id`, `action`, `instruction`, `priority` (int, lower = higher priority), `alert`, `payload` (full `LeadPackResponse`), `generated_at`
- Sort order: alert DESC, action priority ASC, score DESC (same key as `/internal/queue`)
- `limit` applies after sort and after action filter — always truncates from the top of the final sorted list
- `payload` contains the full lead pack (name, email, source, score, rating, summary, next_action, alert, notes, created_at)
- Designed for external automation consumers (n8n, cron jobs) — stable contract for polling and routing
- Excludes leads with active claims (see POST /internal/dispatch/claim)

### POST /internal/dispatch/claim
- Request body: `ClaimRequest` with `lead_ids` (list of int, min 1 item)
- Validates each lead_id exists in leads table before claiming
- Response 200: `ClaimResponse` with three lists:
  - `claimed`: lead_ids successfully claimed in this request
  - `already_claimed`: lead_ids that were already claimed
  - `not_found`: lead_ids that do not exist in leads table
- Claim is permanent — no expiry, no release, no ack
- Claimed leads are excluded from `GET /internal/dispatch` results
- UNIQUE constraint on lead_id — one claim per lead, DB-enforced

---

## Development Rules

- Prefer explicit typing and validation at system boundaries
- Basic tests mandatory before merge: happy path + obvious errors + simple edge cases
- Use format and lint tools consistently across the project
- No new dependencies without clear justification. Each dependency is debt.
- SQL always with bind params (?). Never interpolation.

---

## Security Rules

- Never hardcode secrets. Use environment variables via .env
- Validate all inputs at boundaries (API endpoints)
- API key required on all endpoints

---

> The following sections (approval gates, triada, protected files) are the detailed operational rules
> for the current repo state. They complement the broader constitutional rules in `.claude/CLAUDE.md`.
> If these conflict with `.claude/CLAUDE.md`, the constitution takes precedence on principle;
> these take precedence on operational specifics.

## Human Approval Required

These changes are NOT executed without explicit approval:

- Data model or persisted schema changes (leads table, columns)
- Scoring logic changes (services/scoring)
- Authentication, authorization, API key changes
- Deletion of files, tables, or existing structure
- Docker, docker-compose, CI/CD changes
- Changes to .claude/*, skills/*
- New dependencies
- Refactors affecting multiple modules
- Incompatible changes to public API contracts

---

## Triada (test + review + human approval)

Only applies to high-impact decisions:

- Scoring engine (services/scoring)
- Lead Pack generation (services/leadpack)
- Authentication and authorization

---

## Protected Files

Do not touch without explicit request:
- README.md
- Dockerfile, docker-compose*
- .claude/*, skills/*
- .gitignore

---

## Validation Commands

```bash
python -m pytest tests/api/test_api.py -v   # full API suite
python -m pytest tests/ -v                   # full suite
ruff check .                                 # lint
ruff format .                                # format
```

---

## Known Technical Debt

- Dedup by email+source is at app level, not DB level (no UNIQUE constraint). Theoretical race condition under high concurrency. Acceptable for MVP with SQLite.
- LIKE search (q param) is case-insensitive only for ASCII in SQLite. Sufficient for MVP.
- LIKE wildcards (%, _) are not escaped in q param. Low risk.

---

## Future Phases (recommended order)

1. Minimal API key auth (requires approval)
2. Configurable scoring / extended rules (requires approval)
3. CSV/JSON batch export from GET /leads
4. Webhooks or delivery notifications
5. Market data layer with cache/fallback

---

## Automations MVP (future)

- Triada mode B: scoring_only as default mode
- Configurable subset of scoring rules
- Hard triggers: conditions that automatically escalate to human review

---

## Market Data (future)

- All market data validation must be deterministic and reproducible
- No external data without cache/fallback layer
- Document data source in code
- Does not require triada: deterministic validation is sufficient
