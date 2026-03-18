# Brief: Lead Operations

## Purpose
Operational surfaces for human lead review, prioritization, and follow-up.

## Current scope
- GET /leads/actionable — flat list, score DESC, actionable filter (score>=40 OR has notes)
- GET /leads/actionable/worklist — grouped by next_action in priority order
- GET /internal/queue — flat prioritized: alert DESC → action priority → score DESC
- GET /leads/{id}/operational — single lead operational view
- GET /leads/{id}/pack — full lead detail with rating/summary/action
- GET /leads/summary — aggregate stats with score buckets

## Key files
- `apps/api/services/operational.py` — composition hub (build_operational_summary, get_actionable_leads)
- `apps/api/services/actions.py` — action determination, instructions, priority_reason
- `apps/api/services/leadpack.py` — rating, summary, HTML/text rendering
- `apps/api/routes/leads.py` — worklist grouping (inline, ~15 lines)
- `apps/api/routes/internal.py` — queue sort (_priority_key, inline)

## Contract: LeadOperationalSummary
Fields: lead_id, name, email, source, score, rating, next_action, instruction, priority_reason, alert, summary, phone, created_at, generated_at

## Frozen decisions
- Rating bands: low (<40), medium (40-59), high (>=60) — aligned with action thresholds
- Action thresholds: send_to_client (>=60), review_manually (40-59 with notes), request_more_info (40-59 no notes), enrich_first (<40 with notes), discard (<40 no notes)
- Instructions in Spanish, actionable, operator-focused
- Queue sort: alert DESC → ACTION_PRIORITY order → score DESC
- Worklist groups by next_action in ACTION_PRIORITY order

## Do not touch
- Worklist/queue sort logic (works correctly, inline is fine for current scale)
- Actionable threshold (score>=40 OR has notes) — business rule

## Accepted debt
- No recency tie-breaking in queue sort (business decision pending)
- No lead status tracking (contacted/not contacted)
- Worklist grouping is in routes, not services (acceptable at current scale)

## Likely next block
- Recency tie-breaking (after operator feedback)
- Lead status/contacted tracking (requires DB column)

## See also
- Changing scoring/thresholds? Also read `docs/briefs/leads_core.md`
- Changing queue sort? The sort key is in `routes/internal.py:_priority_key()`
- Adding fields to LeadOperationalSummary? Update `docs/briefs/leads_core.md` frozen decisions
