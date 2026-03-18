# Briefs — Entry Point Index

Read the relevant brief before starting a task. Always read guardrails.md.

| If your task involves... | Read first | Also read |
|---|---|---|
| Lead ingestion, scoring, dedup, storage | leads_core.md | guardrails.md |
| Queue, worklist, actionable, operator view | lead_ops.md | leads_core.md |
| Meta Ads, n8n, webhook ingestion | meta_n8n.md | leads_core.md |
| VPS deploy, backup, health checks, incidents | maintenance_ops.md | guardrails.md |
| Any module / any task | guardrails.md | — |

## When to use briefs vs full docs

- **Brief:** enough for most focused tasks (build, harden, bugfix)
- **Full docs** (CLAUDE.md, context master, decision log): needed for architecture decisions, new module design, or resolving ambiguity between frozen decisions
- **Delta log** (decision_delta_log.md): needed when catching up on recent changes

## Keeping briefs current

Update the relevant brief when closing a block that changes scope, frozen decisions, or accepted debt. Do not update briefs for every small change.
