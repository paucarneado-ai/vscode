# CLAUDE.md — apps/api/automations

## Purpose

Colocated consumer bridge modules for MVP pragmatism.
These are **not** core API business logic.
They consume internal API endpoints as external clients would.

Architecturally, this code belongs outside `apps/api/` — it is placed here
only to minimize repo disturbance during MVP. If more external consumers
appear, this module should move to a top-level `workers/` or `bridges/` directory.

## Invariant

- OpenClaw API = decision layer (scoring, prioritization, contracts)
- This module = consumer/mapper layer (fetch, parse, map, return)
- n8n or other external tools = execution layer (send, schedule, notify)

## Rules

- Do not add business logic here. Trust the API contract.
- Do not re-order, re-filter, re-score, or reinterpret API responses.
- Do not add persistence.
- Do not add sending or scheduling.
- Do not add new dependencies without approval.
- Keep modules narrow: one bridge per consumption surface.

## Current modules

- `followup_bridge.py` — consumes `GET /internal/followup-automation`, maps to execution-ready outputs
