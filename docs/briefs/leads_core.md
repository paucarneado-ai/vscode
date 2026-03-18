# Brief: Leads Core

## Purpose
Lead ingestion, scoring, dedup, and storage engine.

## Current scope
- Intake: web form, webhook/{provider}, webhook/batch, direct POST, batch ingest
- Scoring: deterministic, 0-100, based on source + structured notes fields
- Dedup: (email + source) at app level
- Storage: SQLite single table `leads` (id, name, email, source, notes, score, created_at)
- Normalization: `services/intake.py` (normalize_web_intake, normalize_webhook_payload)
- Persistence: `services/intake.py` (create_lead, query_leads, get_lead_by_id, etc.)

## Key files
- `apps/api/services/intake.py` — normalization + persistence
- `apps/api/services/scoring.py` — score calculation
- `apps/api/services/actions.py` — next_action, alert, instructions, priority_reason
- `apps/api/schemas.py` — all Pydantic models
- `apps/api/db.py` — SQLite connection + schema

## Frozen decisions
- Dedup is email+source at app level (no DB UNIQUE constraint). Accepted MVP debt.
- Score is computed at ingest time, not recalculated on read.
- Notes is unstructured text with `Key: value` line format. No JSON column.
- Source normalization: strip().lower() in intake service, not in routes.
- Rating/action/summary thresholds aligned at 40/60.

## Do not touch
- DB schema (no new columns without explicit approval)
- Scoring thresholds (business decision, requires approval)
- Dedup strategy (changing to DB-level requires migration)

## Accepted debt
- LIKE search wildcards (%, _) not escaped in q param
- Dedup race condition possible under high concurrency (SQLite single-writer mitigates)
- Score not recalculated when scoring rules change (use rescore_leads.py)

## Likely next block
- Structured field extraction from free-text notes (deterministic first, LLM later if justified)
- Lead status tracking (contacted/not contacted) — requires DB schema change

## See also
- Changing scoring rules? Also read `docs/briefs/guardrails.md` (approval required)
- Affecting operational surfaces? Also read `docs/briefs/lead_ops.md`
- Adding a new intake provider? Also read `docs/briefs/meta_n8n.md`
- Considering LLM enrichment? Also read `docs/llm_guardrails.md`
