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
| /leads | GET | OK — filters: source, min_score, limit, offset, q (LIKE on name/email/notes), created_from (YYYY-MM-DD, inclusive), created_to (YYYY-MM-DD, inclusive through end of day). 422 if date format invalid |
| /leads/summary | GET | OK — aggregate stats: total, avg_score, low/medium/high bucket counts. Same filter params as GET /leads (source, min_score, q, created_from, created_to) — same date filter semantics (format, validation, inclusive behavior) |
| /leads/actionable | GET | OK — list of leads with operational summary (next_action, alert, instruction). Supports source, limit filters |
| /leads/actionable/worklist | GET | OK — actionable leads grouped by next_action, priority-ordered |
| /leads/export.csv | GET | OK — CSV export with same filters as GET /leads (including created_from, created_to) |
| /leads/{id} | GET | OK |
| /leads/{id}/pack | GET | OK — JSON with rating and summary |
| /leads/{id}/pack/html | GET | OK — rendered HTML |
| /leads/{id}/pack.txt | GET | OK — plain text |
| /leads/{id}/operational | GET | OK — single lead operational summary (score, rating, next_action, alert, instruction) |
| /leads/{id}/delivery | GET | OK — delivery JSON with embedded pack |
| /internal/queue | GET | OK — flat prioritized queue sorted by alert DESC, action priority ASC, score DESC. Supports source, limit filters. Limit applies after sort |
| /internal/dispatch | GET | OK — automation-ready batch of dispatch payloads with embedded lead packs. Supports source, limit, action filters. Limit applies after sort and filter. Excludes claimed leads |
| /internal/dispatch/claim | POST | OK — claim leads for processing. Validates lead existence. Returns claimed/already_claimed/not_found |
| /internal/dispatch/claim/{lead_id} | DELETE | OK — release an active claim. Returns status: released/not_found/not_claimed |
| /internal/handoffs | GET | OK — outbound-ready handoff batch with channel hint and instruction per lead. Same filters/sort/claim exclusion as dispatch |
| /internal/handoffs/export.csv | GET | OK — CSV export of handoffs. Same filters/sort/claim exclusion as handoffs JSON. Columns: lead_id, action, channel, instruction, name, email, source, score, rating |
| /internal/review | GET | OK — client review queue: only send_to_client and review_manually leads, excludes claimed, sorted by alert DESC then score DESC. Supports source, limit filters. urgent_count reflects full reviewable set before limit |
| /internal/review/{lead_id}/claim | POST | OK — claim a reviewable lead. Validates existence, reviewability, and claim status. Returns status: claimed/already_claimed/not_found/not_reviewable |
| /internal/ops/snapshot | GET | OK — daily ops snapshot: total_leads, actionable, claimed, pending_dispatch, pending_review, urgent. No filters, pure read aggregation |
| /internal/client-ready | GET | OK — client-ready queue: only send_to_client leads, excludes claimed, sorted by score DESC. No filters, flat shape |
| /internal/worklist | GET | OK — operator worklist combining pending_review, client_ready, and recently_claimed in one call. No filters |
| /internal/source-performance | GET | OK — per-source performance breakdown: total, avg_score, client_ready, review. Quality metric independent of claim status. No filters |
| /internal/source-actions | GET | OK — per-source operational recommendations (keep/review) based on MVP heuristics over source-performance signals. No filters |
| /internal/events | GET | OK — recent internal events, newest first. Optional event_type filter, limit (default 50, max 200). Read-only |
| /internal/sentinel | GET | OK — quality sentinel: deterministic read-only operational health checks. Returns status (ok/watch/alert) and findings list. No filters, no side effects |
| /internal/audit | GET | OK — module audit: deterministic cross-module consistency checks. Returns status (pass/warn/fail) and findings list. No filters, no side effects |
| /internal/redundancy | GET | OK — redundancy/waste bot: deterministic read-only report of redundant, overlapping, or absorbed project weight. Scans skills/ and CLAUDE.md hierarchy. No filters, no side effects |
| /internal/scope-critic | POST | OK — scope critic: deterministic structural review of BUILD/HARDEN proposals. Returns status (ok/watch/block) and findings with evidence. No persistence, no side effects |
| /internal/proof-verifier | POST | OK — proof verifier: deterministic post-build review of completion reports. Returns status (close/watch/not_close) and findings with evidence and blocks_closure. No persistence, no side effects |
| /internal/drift-detector | POST | OK — drift detector: deterministic plan-vs-execution cross-reference. Returns status (drift/watch/clean) and findings. Advisory only, no blocking. No persistence, no side effects |
| /internal/outcomes | POST | OK — record or update the real-world outcome for a lead. Upsert semantics (one outcome per lead). Persists to lead_outcomes table |
| /internal/outcomes/summary | GET | OK — aggregated outcome counts across all leads. Returns total and per-outcome counts for all 6 allowed values |
| /internal/outcomes/by-source | GET | OK — outcome counts broken down by lead source. Returns per-source totals with all 6 outcome counts. Read-only, no persistence |
| /internal/followup-queue | GET | OK — retry candidates: leads whose latest outcome is no_answer, excluding claimed leads. Ordered by score DESC. Read-only, reuses get_lead_pack() for operational context |
| /internal/source-outcome-actions | GET | OK — outcome-aware source recommendations. 5 deterministic rules, 3 recommendation values (keep/review/deprioritize). Honest sparsity handling via data_sufficient flag. Read-only, no persistence |
| /internal/daily-actions | GET | OK — compact daily action surface composing review, client-ready, followup, and source warning signals. Each section capped at 5 items. Summary counts reflect pre-cap totals. Read-only, no persistence |
| /internal/followup-handoffs | GET | OK — action handoff surface for no_answer retry candidates. Provides channel, action, instruction, and suggested message per lead. Score-tier templates. Excludes claimed leads. Read-only, no persistence |
| /internal/followup-automation | GET | OK — machine-consumable follow-up payloads for automation consumers. Same selection/ordering as followup-handoffs. Top-level routing fields + nested payload. Priority = relative list position. Read-only, no persistence |
| /demo/intake | GET | OK — demo-only disposable HTML form for POST /leads/external. Exposes name/email/source/phone/notes only (metadata intentionally omitted). Same-origin, no auth, no framework. Not an official frontend surface |

---

## Accepted Contracts

### POST /leads
- Normalizes source (strip + lower) and email (strip + lower) before persisting
- Lightweight deduplication: email + source (post-normalization). Duplicate returns 409 with body LeadCreateResult and meta.status = "duplicate"
- Scoring is calculated with normalized source
- Response 200: LeadCreateResult with meta.status = "accepted"

### GET /leads
- Optional query params: source (exact match), min_score (>= int, ge=0), limit (ge=1), offset (ge=0), q (LIKE %q% on name, email, notes), created_from (YYYY-MM-DD, inclusive), created_to (YYYY-MM-DD, inclusive through end of day via `' 23:59:59'` suffix)
- Date params validated by regex — 422 if format is not YYYY-MM-DD
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
- Claims have no expiry — persist until explicitly released via DELETE /internal/dispatch/claim/{lead_id}
- Claimed leads are excluded from `GET /internal/dispatch` results
- UNIQUE constraint on lead_id — one claim per lead, DB-enforced

### DELETE /internal/dispatch/claim/{lead_id}
- Releases an active claim on a single lead
- Validates lead exists in leads table, then checks for active claim
- Response 200: `ClaimReleaseResponse` with `lead_id` and `status`
- Status values:
  - `released`: claim successfully removed — lead reappears in queues where still eligible
  - `not_found`: lead_id does not exist in leads table
  - `not_claimed`: lead exists but has no active claim
- Release only removes the claim row — does not change scoring, actionability, or reviewability
- After release, lead reappears in dispatch/handoffs/review/client-ready only if it still meets each endpoint's eligibility criteria
- No guarantee of universal reappearance — eligibility depends on the lead's current score and next_action

### GET /internal/handoffs
- Read-only projection of dispatch data into outbound-ready handoffs
- Optional query params: source (exact match, normalized), limit (ge=1), action (exact match on next_action)
- Same sort order as dispatch: alert DESC, action priority ASC, score DESC
- Same claim exclusion as dispatch: claimed leads are filtered out
- Returns `HandoffBatchResponse`: `generated_at`, `total`, `items`
- Each item is `HandoffItem`: `lead_id`, `action`, `channel`, `instruction`, `payload` (full `LeadPackResponse`)
- Channel mapping: `send_to_client` → `email`, `review_manually` → `review`, `request_more_info` → `email`, `enrich_first` → `manual`, unknown → `manual`
- Instruction: short operational text including lead name, source, and score
- No persistence, no side effects — pure read endpoint

### GET /internal/review
- Read-only client review queue for human commercial review
- Only includes leads where `next_action` is `send_to_client` or `review_manually`
- Excludes claimed leads
- Optional query params: source (exact match, normalized), limit (ge=1)
- Sort order: alert DESC, score DESC
- Returns `ReviewQueueResponse`: `generated_at`, `total`, `urgent_count`, `items`
- Each item is `ReviewItem`: `lead_id`, `name`, `email`, `source`, `score`, `rating`, `next_action`, `instruction`, `alert`, `created_at`
- `urgent_count` reflects the full reviewable unclaimed set before limit truncation
- `total` reflects the number of items returned (after limit)
- No persistence, no side effects — pure read endpoint

### POST /internal/review/{lead_id}/claim
- Claims a single lead from the review queue
- Validates lead exists in leads table, is reviewable (`next_action` in `send_to_client`, `review_manually`), and is not already claimed
- Response 200: `ReviewClaimResponse` with `lead_id` and `status`
- Status values:
  - `claimed`: lead successfully claimed — now excluded from review, dispatch, and handoffs
  - `already_claimed`: lead was already claimed
  - `not_found`: lead_id does not exist in leads table
  - `not_reviewable`: lead exists but `next_action` is not `send_to_client` or `review_manually`
- Reuses `dispatch_claims` table — claimed leads are excluded from all dispatch/handoff/review endpoints

### GET /internal/worklist
- Read-only operator worklist combining three sections in one call
- No query params
- Returns `OperatorWorklistResponse`: `generated_at`, `pending_review`, `client_ready`, `recently_claimed`
- `pending_review`: `ReviewItem[]` — same set as `/internal/review` (reviewable + unclaimed, alert DESC / score DESC)
- `client_ready`: `ClientReadyItem[]` — same set as `/internal/client-ready` (send_to_client + unclaimed, score DESC)
- `recently_claimed`: `WorklistClaimedItem[]` — last 10 claims by `claimed_at DESC`. Each item: `lead_id`, `name`, `source`, `score`, `claimed_at`
- Identity: `pending_review` lead_ids == `/internal/review` lead_ids; `client_ready` lead_ids == `/internal/client-ready` lead_ids
- No persistence, no side effects — pure read endpoint

### GET /internal/client-ready
- Read-only queue of leads ready for client delivery
- No query params — returns all unclaimed leads with `next_action == "send_to_client"`
- Returns `ClientReadyResponse`: `generated_at`, `total`, `items`
- Each item is `ClientReadyItem`: `lead_id`, `name`, `email`, `source`, `score`, `rating`, `next_action`, `instruction`, `created_at`
- `next_action` is always `send_to_client` (explicit in each item per contract)
- Sort: score DESC
- Excludes claimed leads (same `dispatch_claims` exclusion as dispatch/handoffs/review)
- Identity: lead_ids == handoffs with `action=send_to_client` lead_ids
- No persistence, no side effects — pure read endpoint

### GET /internal/ops/snapshot
- Read-only operational snapshot for daily ops visibility
- No query params — returns a single aggregated view of the full system
- Returns `OpsSnapshotResponse`: `generated_at`, `total_leads`, `actionable`, `claimed`, `pending_dispatch`, `pending_review`, `urgent`
- `total_leads`: COUNT of all leads in the database (regardless of score or actionability)
- `actionable`: count of leads meeting actionability criteria (score >= 40 OR has notes)
- `claimed`: count of leads with active dispatch claims
- `pending_dispatch`: actionable minus claimed (unclaimed actionable leads)
- `pending_review`: unclaimed actionable leads where `next_action` is `send_to_client` or `review_manually`
- `urgent`: unclaimed actionable leads where `alert` is true — **not** limited to review queue; covers all actionable unclaimed leads with alert=true
- Identity: `pending_dispatch == actionable - claimed`
- No persistence, no side effects — pure read endpoint

### GET /internal/source-performance
- Read-only per-source performance breakdown
- No query params — returns all sources
- Returns `SourcePerformanceResponse`: `generated_at`, `total_sources`, `items`
- Each item is `SourceStats`: `source`, `total`, `avg_score`, `client_ready`, `review`
- `total`: count of all leads from this source (regardless of actionability)
- `avg_score`: average score of all leads from this source, rounded to 1 decimal
- `client_ready`: count of actionable leads from this source where `next_action == "send_to_client"` — **independent of claim status**
- `review`: count of actionable leads from this source where `next_action == "review_manually"` — **independent of claim status**
- `client_ready` and `review` measure source quality, not operational queue state. Claiming a lead does not change these counts.
- Sort: total DESC
- No persistence, no side effects — pure read endpoint

### GET /internal/source-actions
- Read-only per-source operational recommendations
- No query params — returns all sources
- Returns `SourceActionResponse`: `generated_at`, `total_sources`, `items`
- Each item is `SourceActionItem`: `source`, `total`, `actionable`, `avg_score`, `client_ready`, `review`, `recommendation`, `rationale`
- `actionable`: count of actionable leads from this source (score >= 40 OR has notes)
- `recommendation`: `"keep"` or `"review"` — no `deprioritize` under current scoring model
- `rationale`: deterministic short phrase explaining which rule fired
- Recommendation rules are **MVP heuristics**, not stable business policy. They are derived from current source-performance signals and will need tuning as the scoring model and lead volume evolve.
- Rule evaluation order (first match wins):
  1. `actionable < 3` → `review` / `"insufficient data"`
  2. `client_ready / actionable >= 0.5` → `keep` / `"high client_ready rate"`
  3. `avg_score >= 55` → `keep` / `"strong avg score"`
  4. `review / actionable >= 0.3` → `review` / `"high review rate"`
  5. default → `review` / `"no strong signal"`
- `client_ready` and `review` are independent of claim status (same semantics as `/internal/source-performance`)
- Ratios use `actionable` as denominator, not `total`, to avoid mixing populations
- Known debt: under current scoring (base 50, +10 for notes), `actionable == total` always. If scoring changes to allow sub-40 scores, a `deprioritize` category should be considered.
- Sort: total DESC (inherited from source-performance data)
- No persistence, no side effects — pure read endpoint

### Internal Event Spine
- Append-only event log stored in `events` table (SQLite)
- One helper: `emit_event(event_type, entity_type, entity_id, origin_module, payload)` in `apps/api/events.py`
- Best-effort: emit failures are silently swallowed — primary operations (lead creation, claim, release) are never blocked by event insertion failure
- This is operational traceability, not a guaranteed audit ledger. Events may be silently lost if the database is unavailable or the emit call fails. Do not treat the event log as authoritative proof that an operation occurred.
- No subscribers, no handlers, no retry, no background processing

### Event Contract
- `event_type`: dotted string (e.g. `lead.created`)
- `entity_type`: string (e.g. `lead`)
- `entity_id`: integer reference to the entity
- `origin_module`: string identifying the emitting module (e.g. `leads`, `dispatch`, `review`)
- `payload`: JSON object — minimal, no PII
- `created_at`: ISO 8601 UTC timestamp

### Current Event Types
| Event Type | Entity Type | Origin | Payload | Emitted When |
|---|---|---|---|---|
| lead.created | lead | leads | `{"source": "...", "score": N}` | New lead successfully created (not on duplicate) |
| lead.claimed | lead | dispatch | `{}` | Lead claimed via POST /internal/dispatch/claim |
| lead.claimed | lead | review | `{}` | Lead claimed via POST /internal/review/{lead_id}/claim |
| lead.released | lead | dispatch | `{}` | Claim released via DELETE /internal/dispatch/claim/{lead_id} |
| lead.outcome_recorded | lead | outcomes | `{"outcome": "<value>"}` | Outcome recorded or updated via POST /internal/outcomes |

### Payload Rules
- No PII (no name, no email) in event payloads — the event log is append-only and cannot be purged per-record
- `lead.created` carries only `source` and `score` — minimum needed to understand what happened without re-querying
- `lead.claimed` and `lead.released` carry empty payload — the event itself is the signal, `entity_id` and `origin_module` provide full context

### GET /internal/events
- Read-only list of recent internal events
- Optional query params: `event_type` (exact match), `limit` (default 50, ge=1, le=200)
- Returns `EventListResponse`: `generated_at`, `total`, `items`
- Each item is `EventItem`: `id`, `event_type`, `entity_type`, `entity_id`, `origin_module`, `payload` (dict), `created_at`
- Sort: id DESC (newest first)
- `total` reflects items returned (after limit)
- No persistence, no side effects — pure read endpoint

### GET /internal/sentinel
- Read-only quality sentinel — deterministic operational health checks
- No query params
- Returns `SentinelResponse`: `generated_at`, `status`, `total_findings`, `findings`
- `status`: derived from highest severity finding — `alert` if any high, `watch` if any medium, `ok` otherwise
- Each finding is `SentinelFinding`: `check`, `surface`, `severity`, `message`, `recommended_action`
- `severity`: `low`, `medium`, or `high`
- No persistence, no side effects, no auto-remediation — pure read endpoint

### Sentinel Checks
| Check | Surface | Severity | Description |
|---|---|---|---|
| stale_claims | dispatch | low/medium | Active claims older than 24h. Medium if >3, low otherwise. 24h threshold is an MVP operational heuristic, not a stable policy or SLA. |
| source_needs_attention | source-actions | low | Sources with recommendation=review and sufficient data (rationale != insufficient data). Current attention signal, not drift detection. |
| event_spine_silent | events | high/medium | Two rules: (1) HIGH — leads exist but zero events ever recorded. (2) MEDIUM — leads created in the last 24h exist but zero events recorded in that window (historical events exist but recent activity is silent). 24h window matches the stale_claims threshold. |

### Known Debt
- Index exists on `event_type`. No index on `entity_id` — acceptable for MVP volume, add if per-entity event lookup becomes a real use case
- No event pruning or retention policy — append-only with no cleanup
- `source.*` computed events deferred — they are aggregations, not state transitions

### GET /internal/audit
- Read-only module audit — deterministic cross-module consistency checks
- No query params
- Returns `AuditResponse`: `generated_at`, `status`, `total_findings`, `findings`
- `status`: derived from highest severity finding — `fail` if any high, `warn` if any medium, `pass` otherwise
- Each finding is `AuditFinding`: `check`, `surface`, `severity`, `message`, `detail`
- `detail`: dict with structured information about the inconsistency
- No persistence, no side effects — pure structural invariant checks

### Audit Checks
| Check | Surface | Severity | Description |
|---|---|---|---|
| source_surface_consistency | source-performance / source-actions | medium | Source list and per-source totals must agree between the two surfaces. Both query the same base data; a mismatch indicates a bug in one aggregation path. |
| ops_snapshot_arithmetic | ops/snapshot | high | pending_dispatch must equal actionable - claimed. Violation indicates a logic bug in snapshot assembly. |

### Audit Known Debt
- Only 2 checks in MVP. Event-based coherence checks deferred — best-effort emission makes them structurally weak.
- No historical comparison — checks are point-in-time invariants only.

### GET /internal/redundancy
- Read-only redundancy/waste report — deterministic filesystem inspection
- No query params
- Returns `RedundancyResponse`: `generated_at`, `areas_scanned`, `overall_status`, `total_findings`, `findings`
- `overall_status`: derived from highest severity finding — `alert` if any high, `watch` if any medium, `ok` otherwise
- Each finding is `RedundancyFinding`: `type`, `targets`, `severity`, `message`, `recommended_action`, `confidence`, `removal_risk`, `why_now`
- `type`: `overlap`, `dormant`, `low_value`, `candidate_archive`, `candidate_delete`
- `recommended_action`: `keep`, `merge`, `archive_candidate`, `delete_candidate`
- `confidence`: `low`, `medium`, `high`
- `removal_risk`: `low`, `medium`, `high` — how risky it would be to remove this item
- `why_now`: short reason why this candidate matters now
- No persistence, no side effects, no file modifications — pure read endpoint

### Redundancy Checks

Each finding is a `RedundancyFinding` with field `type` (not `check`). The `type` field indicates the kind of redundancy detected.

| Internal check | Finding `type` | Area | Severity | Description |
|---|---|---|---|---|
| Skills redundant candidates | `overlap` | skills/ | low | Reports skills from an explicit hardcoded candidate list whose purpose is fully absorbed by current .claude/CLAUDE.md governance. Not discovered by fuzzy matching — candidates are human-curated. `recommended_action=archive_candidate`. |
| Dormant stubs | `dormant` | CLAUDE.md hierarchy | low | Reports CLAUDE.md files that explicitly declare themselves as stubs (contain literal marker). Deterministic, not guesswork. `recommended_action=keep`. |
| CLAUDE.md literal duplication | `overlap` | CLAUDE.md hierarchy | low | Finds module-local CLAUDE.md files with ≥2 literal rule duplicates from the global .claude/CLAUDE.md. Near-literal match after normalizing whitespace, bullets, numbering, and casing. Does NOT flag local rules that are more restrictive or more procedural than the global rule. `recommended_action=merge`. |

### Redundancy Known Debt
- Candidate list is static — must be manually updated when skills are added/removed or governance changes.
- Only scans skills/ and CLAUDE.md hierarchy. Does not inspect helper code, operational rules, or docs for redundancy.
- No fuzzy or semantic analysis — only exact candidate matching and literal text comparison.

### POST /internal/scope-critic
- Deterministic structural review of BUILD/HARDEN proposals — no persistence, no side effects
- Request body `ScopeCriticRequest`: all 7 fields required and non-empty — `classification`, `goal`, `scope` (list), `out_of_scope` (list), `expected_files` (list), `main_risk`, `minimum_acceptable`
- Returns `ScopeCriticResponse`: `generated_at`, `status`, `total_findings`, `findings`
- `status`: `block` if any high severity, `watch` if any medium, `ok` otherwise
- Each finding is `ScopeCriticFinding`: `check`, `severity`, `message`, `evidence` (list[str])
- `evidence` provides structured pointers to what triggered the finding

### Scope Critic Checks
| Check | Severity | Description |
|---|---|---|
| sensitive_file_intrusion | high | Protected files in expected_files must have their area explicitly in scope and not contradicted by out_of_scope. Protected patterns: `.claude/*`, `skills/*`, `README.md`, `Dockerfile`, `docker-compose*`, `.gitignore`. |
| file_spread_risk | medium | Expected files spanning >4 distinct repo areas. Areas are repo-aware: `.claude`, `skills`, `docs`, `tests`, `apps/api`, `apps/api/routes`, `apps/api/services`, `apps/api/automations`, `core`, `deploy`, `root`. Longest-prefix match. |
| weak_out_of_scope | medium | All out_of_scope entries are trivially dismissive placeholders (nothing, none, n/a, na, tbd, -). At least one substantive entry prevents firing. |
| minimum_scope_mismatch | medium | Generic placeholder minimum_acceptable (tbd, get it working, make it work, whatever works, just do it, same as goal, see above, see goal) combined with non-trivial scope (>2 items) or expected_files (>3 items). Both conditions required. |
| risk_unacknowledged | low | main_risk is a trivially dismissive value. Extends the dismissive set with: no risk, low risk, low, none expected. |

### Scope Critic Known Debt
- Area mapping is static — must be updated if repo structure changes.
- Placeholder lists are explicit and finite — new placeholder patterns require code update.
- Does not validate that expected_files actually exist on disk — reviews proposal structure only.

### POST /internal/proof-verifier
- Deterministic post-build review of completion reports — no persistence, no side effects, no file modifications
- Request body `ProofVerifierRequest`: `block_name` (required), `classification` (required), `claimed_changes` (list, required non-empty), `claimed_verified` (list, required non-empty), `claimed_not_verified` (list, can be empty), `files_touched` (list, required non-empty), `tests_run` (list, can be empty), `status_claim` (required)
- Returns `ProofVerifierResponse`: `generated_at`, `status`, `total_findings`, `findings`
- `status`: `not_close` if any finding has `blocks_closure=True`, `watch` if any medium/high severity, `close` otherwise
- Each finding is `ProofVerifierFinding`: `check`, `severity`, `message`, `evidence` (list[str]), `blocks_closure` (bool), `confidence` (low/medium/high)
- File-to-evidence matching uses specific path substring (full path > parent/basename > basename), not area-level

### Proof Verifier Checks
| Check | Severity | blocks_closure | Description |
|---|---|---|---|
| unverified_gap | high | yes | claimed_not_verified is non-empty but status_claim uses closure language (done, complete, production-ready, fully verified, fully supported, no debt). Contradiction between admitting gaps and claiming closure. |
| untested_changes | medium | no | Files in files_touched with no specific mention (path substring match) in tests_run or claimed_verified. Reports unmatched files as evidence. **Resolution:** include the file path or basename in at least one `claimed_verified` or `tests_run` item (e.g., "Doc change in operational_contracts.md reviewed: ..."). |
| empty_test_evidence | high | yes | tests_run is empty AND claimed_verified contains no test-like references (keyword stems with prefix word-boundary matching: test, pytest, check, verif, spec, assert). No test evidence provided at all. |
| overclaim_status | low | no | status_claim uses overconfident language warned against in anti-complacency rules (complete, production-ready, fully supported, no debt, done). |
| verification_claim_mismatch | medium | no | claimed_not_verified is empty (claiming zero gaps) but fewer than half of files_touched have specific verification evidence. Claim/evidence contradiction. |

### Proof Verifier Known Debt
- File-to-evidence matching is substring-based — can produce false matches on short basenames.
- Test evidence keyword detection uses prefix word-boundary matching — prevents "inspected" from matching "spec", but stem-based so "tested" matches "test".
- Does not verify that tests actually passed — trusts the report structure.
- Closure/overclaim language lists are static and finite.

---

### POST /internal/drift-detector
- Deterministic plan-vs-execution cross-reference — advisory only, no persistence, no side effects
- Request body `DriftDetectorRequest`: `plan_expected_files` (list, required non-empty), `plan_out_of_scope` (list, required non-empty), `plan_classification` (required), `report_files_touched` (list, required non-empty), `report_claimed_changes` (list, required non-empty), `report_classification` (required)
- Returns `DriftDetectorResponse`: `generated_at`, `status`, `total_findings`, `findings`
- `status`: `drift` if any finding has severity high, `watch` if any medium, `clean` otherwise
- Each finding is `DriftFinding`: `check`, `severity`, `message`, `plan_value` (list[str]), `report_value` (list[str]), `requires_justification` (bool, always true in v1)
- Advisory only — does not block closure. The human decides.

### Drift Detector Checks
| Check | Severity | Description |
|---|---|---|
| file_addition_drift | high | Files in report_files_touched not in plan_expected_files. Path normalization: lowercase, strip, forward-slash, no trailing slash. |
| file_omission_drift | medium | Files in plan_expected_files not in report_files_touched. Same normalization. |
| classification_drift | medium | plan_classification != report_classification after lowercase/strip normalization. |
| out_of_scope_intrusion | high | Items in report_claimed_changes that exactly match items in plan_out_of_scope after text normalization (lowercase, strip, collapse whitespace). No substring matching. No fuzzy matching. |

### Drift Detector Known Debt
- out_of_scope_intrusion uses exact normalized matching only — will miss semantic drift where different wording describes the same concept. Conservative by design for v1.
- Not yet integrated into the REVIEW FLOW constitution (apps/api/CLAUDE.md). Must be called manually.
- No governance promotion yet — endpoint exists but is not referenced by system_map.md, component_index.md, or CLAUDE.md review flow.

---

### POST /internal/outcomes

Records the real-world outcome for a lead. Upsert semantics — one outcome per lead, latest write wins.

**Request:**

| Field | Type | Required | Notes |
|---|---|---|---|
| lead_id | integer | yes | Must reference existing lead |
| outcome | string | yes | One of: contacted, qualified, won, lost, no_answer, bad_fit |
| reason | string | no | Free text explaining why this outcome |
| notes | string | no | Optional additional context |

**Response (201):**

| Field | Type |
|---|---|
| lead_id | integer |
| outcome | string |
| reason | string or null |
| notes | string or null |
| recorded_at | ISO 8601 timestamp |

**Errors:** 404 if lead_id does not exist. 422 if outcome is not in allowed set or lead_id is missing.

**Persistence:** `lead_outcomes` table. `lead_id` is PK. Uses `ON CONFLICT(lead_id) DO UPDATE` for upsert.

### GET /internal/outcomes/summary

Aggregated outcome counts across all leads.

**Response (200):**

| Field | Type |
|---|---|
| generated_at | ISO 8601 timestamp |
| total | integer |
| by_outcome | object — keys are all 6 allowed outcomes, values are integer counts (0 if none) |

**Allowed outcomes:** contacted, qualified, won, lost, no_answer, bad_fit

**Known debt:**
- No per-lead outcome read endpoint yet — summary only.
- No outcome history — upsert overwrites previous outcome silently.
- Emits `lead.outcome_recorded` event with payload `{"outcome": "<value>"}` on each write.
- No filtering by source, date range, or score on summary.

### GET /internal/outcomes/by-source

Outcome counts broken down by lead source. Read-only.

**Response (200):**

| Field | Type |
|---|---|
| generated_at | ISO 8601 timestamp |
| total_sources | integer |
| items | array of source outcome items |

**Each item:**

| Field | Type |
|---|---|
| source | string |
| total | integer |
| contacted | integer |
| qualified | integer |
| won | integer |
| lost | integer |
| no_answer | integer |
| bad_fit | integer |

**Behavior:** Items ordered alphabetically by source. All 6 outcome keys present with 0 counts for unused outcomes. Only sources with at least one recorded outcome appear.

**Known debt:**
- No date filtering.
- No score breakdown within source.
- Sources with zero outcomes do not appear (only sources with at least one recorded outcome are included).

### GET /internal/followup-queue

Retry candidates: leads whose latest outcome is `no_answer`. Read-only.

**Response (200):**

| Field | Type |
|---|---|
| generated_at | ISO 8601 timestamp |
| total | integer |
| items | array of followup items |

**Each item:**

| Field | Type | Source |
|---|---|---|
| lead_id | integer | leads table |
| name | string | leads table |
| email | string | leads table |
| source | string | leads table |
| score | integer | leads table |
| rating | string | get_lead_pack() |
| next_action | string | get_lead_pack() |
| instruction | string | get_instruction() |
| outcome | string | always "no_answer" |
| outcome_reason | string or null | lead_outcomes table |
| outcome_notes | string or null | lead_outcomes table |
| outcome_recorded_at | ISO 8601 timestamp | lead_outcomes table |

**Behavior:** Ordered by score DESC, lead_id ASC as tie-breaker. Only includes leads with `outcome = 'no_answer'`. Claimed leads are excluded (same pattern as dispatch, handoffs, review, client-ready). If outcome is updated (upserted) to a different value, lead leaves the queue.

**Known debt:**
- No pagination.
- No date filtering.
- N+1 query pattern (one `get_lead_pack()` call per lead). Acceptable for MVP scale.
- Does not distinguish first-time no_answer from repeated no_answer (no retry counter).

### GET /internal/source-outcome-actions

**Purpose:** Outcome-aware source recommendations. Unlike `/internal/source-actions` (proxy-only: score, action distribution), this endpoint uses real recorded outcomes to recommend whether to keep, review, or deprioritize a source.

**Response shape:**
```json
{
  "generated_at": "...",
  "total_sources": 1,
  "items": [
    {
      "source": "web",
      "total_outcomes": 10,
      "contacted": 2,
      "qualified": 3,
      "won": 2,
      "lost": 1,
      "no_answer": 1,
      "bad_fit": 1,
      "recommendation": "keep",
      "rationale": "strong qualified/won signal (50%)",
      "data_sufficient": true
    }
  ]
}
```

**Recommendation rules (evaluated in order, first match wins):**

| Rule | Condition | Recommendation | Rationale |
|------|-----------|---------------|-----------|
| R1 | total_outcomes < 3 | review | insufficient outcome data |
| R2 | (won + qualified) / total >= 50% | keep | strong qualified/won signal |
| R3 | (bad_fit + lost) / total >= 50% | deprioritize | high bad_fit/lost rate |
| R4 | no_answer / total >= 50% | review | high no_answer rate |
| R5 | none of above | review | mixed outcome pattern |

**Key fields:**
- `data_sufficient`: `false` when R1 fires (< 3 outcomes). Explicit honesty signal.
- `total_outcomes`: count of leads with recorded outcomes for this source, not total leads.
- Items sorted alphabetically by source name.

**Behavior:** Read-only. No persistence. Reuses same SQL pattern as `/internal/outcomes/by-source`. Only sources with at least one recorded outcome appear.

**Known debt:**
- Minimum data threshold (3) is deliberately low for MVP. May need raising as volume grows.
- Sources with no recorded outcomes do not appear (no "no data" row).
- No date filtering — recommendations use all-time outcome data.
- No proxy field integration — consumer must cross-reference with `/internal/source-actions` for proxy signals.

### GET /internal/daily-actions

**Purpose:** Compact daily action surface that answers "what should we do today?" by composing existing operational signals into one response. Not a dashboard — a prioritized action view.

**Response shape:**
```json
{
  "generated_at": "...",
  "summary": {
    "pending_review": 3,
    "client_ready": 4,
    "followup_candidates": 5,
    "source_warnings": 2
  },
  "top_review": [
    { "lead_id": 1, "name": "...", "source": "...", "score": 80, "rating": "high", "next_action": "review_manually", "alert": true }
  ],
  "top_client_ready": [
    { "lead_id": 2, "name": "...", "source": "...", "score": 90, "rating": "high", "next_action": "send_to_client" }
  ],
  "top_followup": [
    { "lead_id": 3, "name": "...", "source": "...", "score": 70, "outcome_recorded_at": "..." }
  ],
  "source_warnings": [
    { "source": "web", "recommendation": "deprioritize", "rationale": "high bad_fit/lost rate (60%)", "total_outcomes": 10 }
  ]
}
```

**Sections:**

| Section | Contents | Ordering | Cap |
|---------|----------|----------|-----|
| `top_review` | Unclaimed leads with `next_action == "review_manually"` | Priority sort (alert DESC, action priority, score DESC) | 5 |
| `top_client_ready` | Unclaimed leads with `next_action == "send_to_client"` | Priority sort | 5 |
| `top_followup` | Leads with `outcome = 'no_answer'`, unclaimed | Score DESC, lead_id ASC | 5 |
| `source_warnings` | Sources with `review` or `deprioritize` recommendation and `data_sufficient=True` | Alphabetical by source | No cap |

**Summary:** `pending_review`, `client_ready`, `followup_candidates` reflect full pre-cap counts. `source_warnings` count equals section length (no cap applied).

**Naming note:** `summary.pending_review` here counts only `review_manually` leads. This differs from `/ops/snapshot.pending_review`, which counts both `review_manually` and `send_to_client`. The relationship is: `snapshot.pending_review == daily_actions.pending_review + daily_actions.client_ready`.

**Behavior:** Read-only composition surface. No persistence. Reuses `_get_actionable_leads()`, `_get_claimed_lead_ids()`, `_source_outcome_recommendation()`. Claimed leads excluded from all sections.

**Known debt:**
- No date filtering — shows all-time state.
- N+1 avoidance: followup section uses direct SQL join instead of `get_lead_pack()` to keep the item shape minimal.
- Source warnings do not include `keep` sources (by design — only actionable warnings shown).
- Cap of 5 is hardcoded. Acceptable for MVP.

### GET /internal/followup-handoffs

**Purpose:** Action handoff surface for no_answer retry candidates. Tells the operator what to do, which channel to use, and what to say — without sending anything.

**Response shape:**
```json
{
  "generated_at": "...",
  "total": 1,
  "items": [
    {
      "lead_id": 12,
      "name": "Alice",
      "email": "alice@example.com",
      "source": "web",
      "score": 60,
      "rating": "medium",
      "outcome_recorded_at": "...",
      "channel": "email",
      "action": "retry_contact",
      "instruction": "Retry contact — send a short follow-up email",
      "suggested_message": "Hi Alice, following up on my previous message..."
    }
  ]
}
```

**Deterministic logic:**
- `channel`: always `"email"` (MVP default — no phone/WhatsApp signal in data model)
- `action`: always `"retry_contact"`
- `instruction` and `suggested_message`: vary by rating tier (uses system `get_rating()` vocabulary)

| Rating | Instruction | Message tone |
|--------|-------------|-------------|
| `high` (≥75) | Retry contact — high-value lead, send personalized follow-up email | Personal, strong-fit emphasis |
| `medium` (50–74) | Retry contact — send a short follow-up email | Neutral follow-up |
| `low` (<50) | Retry contact — send a brief check-in email, consider deprioritizing if no response | Low-effort, suggests deprioritization |

**Behavior:** Read-only. No persistence. Only includes leads with `outcome = 'no_answer'`. Claimed leads excluded. Ordered by score DESC, lead_id ASC.

**Known debt:**
- Channel is hardcoded to `"email"` — no multi-channel logic.
- Suggested messages are static templates — no personalization beyond name.
- No retry counter — does not track how many times a lead has been retried.
- No pagination.

### GET /internal/followup-automation

**Purpose:** Machine-consumable follow-up payloads for automation consumers (n8n, workers, external systems). Same selection and ordering as `/internal/followup-handoffs`, reshaped for machine routing.

**Response shape:**
```json
{
  "generated_at": "...",
  "total": 1,
  "items": [
    {
      "lead_id": 12,
      "channel": "email",
      "action": "retry_contact",
      "priority": 0,
      "payload": {
        "name": "Alice",
        "email": "alice@example.com",
        "source": "web",
        "score": 60,
        "rating": "medium",
        "instruction": "Retry contact — send a short follow-up email",
        "suggested_message": "Hi Alice, following up on my previous message..."
      }
    }
  ]
}
```

**Key fields:**
- `channel`, `action`: top-level routing fields for machine consumers to dispatch on.
- `priority`: relative list position (0 = highest). Derived from current score-sorted ordering — **not a persistent workflow priority**. Value may change between calls as leads are added, claimed, or outcomes updated.
- `payload`: nested object with everything needed to execute (identity, context, content).

**Behavior:** Read-only. No persistence. Same selection as followup-handoffs: leads with `outcome = 'no_answer'`, excluding claimed, ordered by score DESC, lead_id ASC. Same instruction/message templates (score-tier based via `get_rating()`).

**Known debt:**
- Channel hardcoded to `"email"`.
- No pagination.
- No retry counter.
- Does not send or schedule — pure payload surface.

### Follow-up Automation Bridge (apps/api/automations/followup_bridge.py)

**Purpose:** Minimal consumer bridge that validates GET /internal/followup-automation is programmatically consumable. Fetches, parses, and maps automation items into execution-ready outputs. Does not send, schedule, or mutate anything.

**Interface:**

    def run_followup_bridge(client) -> BridgeResult:
        # client must have .get(path) returning response with .status_code and .json()

**Output contract:**
- BridgeItem: lead_id, to (email), subject (deterministic from rating), body (suggested_message), channel, priority, source, score, rating
- BridgeResult: fetched_at, total_fetched, total_mapped, items (list of BridgeItem), errors (list of str)

**Subject mapping (deterministic):**

| Rating | Subject |
|--------|---------|
| high | Following up — let's connect this week |
| medium | Quick follow-up |
| low | Checking in |
| (other) | Follow-up (fallback — defensive default for unrecognized ratings; not triggered by current API) |

**`total_fetched` semantics:** reflects the API-declared `total` field exactly, not `len(items)`. These may differ if the API applies limits or if individual items are malformed and skipped. `total_mapped` reflects the count of successfully mapped items.

**Top-level validation:** the bridge requires the response to be a dict with `generated_at` (str), `total` (int), and `items` (list). Any violation is a global failure.

**Key behaviors:**
- Read-only. Does not send, mutate, or persist anything.
- Ordering is trusted from the API and not recomputed.
- Non-200 response: global failure with error.
- Invalid top-level shape (missing/wrong-typed `generated_at`, `total`, or `items`): global failure with error.
- Invalid individual item: skip that item, record error, continue mapping the rest.
- Colocated under `apps/api/automations/` for MVP pragmatism. Not core API business logic.
- `apps/api/automations/CLAUDE.md` is no longer a dormant stub — it was replaced with real governance content when this bridge was built. The redundancy scanner's dormant-stub expectation was updated accordingly (truth-alignment change, not a product semantic change).

**Known debt:**
- Idempotency is out of scope. Nothing is sent, so dedup is not yet needed. When a real sender is added, dedup by lead_id and execution window becomes mandatory.
- Channel is whatever the API exposes (email currently). No multi-channel abstraction.
- No retry logic, no scheduling, no queue infrastructure.
- Module may need to move outside apps/api/ if more external consumers appear.

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
