# Brief: Cross-Cutting Guardrails

Global rules that apply regardless of which module you're working on.

## Approval required before implementing

- DB schema changes (new columns, tables, constraints)
- Scoring logic or threshold changes
- Auth/authorization changes
- Deleting files, tables, or structure
- Docker/CI/CD changes
- New dependencies
- Changes to .claude/*, skills/*
- Breaking changes to public API contracts

## Never do

- Hardcode secrets (use env vars via .env)
- SQL without bind params (always use ?)
- Introduce LLM runtime calls without proving deterministic is insufficient (see docs/llm_guardrails.md)
- Create new lead views/projections without clear functional delta vs existing surfaces
- Refactor outside the scope of the current task

## Always do

- Tests before merge: happy path + obvious errors + simple edge cases
- Validate inputs at API boundaries
- Declare which files change before implementing
- Mark deferred debt explicitly in deliverables

## Protected files (do not touch without explicit request)

- README.md
- Dockerfile, docker-compose*
- .claude/*, skills/*
- .gitignore

## Caddy public surface

Only `POST /api/leads/intake/web` is publicly routed. All other `/api/*` returns 403. Do not open new public routes without explicit approval.

## Cost discipline

No step that adds cost-per-lead or latency is acceptable without clear improvement in quality, conversion, or risk reduction. See docs/llm_guardrails.md for LLM-specific rules.
