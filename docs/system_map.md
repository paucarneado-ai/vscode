# System Map

> Navigation layer for the OpenClaw repo.
> Not a rewrite of docs. Not a README. A retrieval tool.
>
> If you need the contract for an endpoint, go to `docs/operational_contracts.md`.
> If you need a frozen decision, go to `docs/leads_decision_log.md`.
> If you need operational procedures, go to `docs/leads_runbook.md`.
> This file tells you *where to look* and *what things are called*.

Last verified: 2026-03-16 — 495 tests passing.

---

## Exact Names / Named Constructs

Quick-reference for recovering exact names, types, and locations. If you're looking for something and can't remember what it's called, check here first.

| Exact name | Type | Location | One-line purpose |
|------------|------|----------|------------------|
| Internal Event Spine | Shared cross-module construct | `apps/api/events.py` (code), `docs/operational_contracts.md` → "Internal Event Spine" (contract) | Append-only event log with best-effort `emit_event()` — operational traceability across modules |
| Follow-up Automation Bridge | Consumer bridge module | `apps/api/automations/followup_bridge.py` | Consumes `/internal/followup-automation`, maps to execution-ready output for external tools |
| Sentinel | Quality bot (endpoint) | `apps/api/routes/internal.py` → `GET /internal/sentinel` | Deterministic operational health checks (stale claims, source attention, event spine silence) |
| Audit | Quality bot (endpoint) | `apps/api/routes/internal.py` → `GET /internal/audit` | Deterministic cross-module consistency checks (source agreement, ops arithmetic) |
| Redundancy | Quality bot (endpoint) | `apps/api/routes/internal.py` → `GET /internal/redundancy` | Filesystem scan for absorbed skills, dormant stubs, CLAUDE.md duplication |
| Scope Critic | Governance bot (endpoint) | `apps/api/routes/internal.py` → `POST /internal/scope-critic` | Pre-build structural review of BUILD/HARDEN proposals |
| Proof Verifier | Governance bot (endpoint) | `apps/api/routes/internal.py` → `POST /internal/proof-verifier` | Post-build closure review of completion reports |
| Drift Detector | Governance bot (endpoint) | `apps/api/routes/internal.py` → `POST /internal/drift-detector` | Plan-vs-execution cross-reference — advisory only, not yet in review flow |
| Daily Actions | Composition surface (endpoint) | `apps/api/routes/internal.py` → `GET /internal/daily-actions` | "What should we do today?" — capped review + client-ready + followup + source warnings |
| Ops Snapshot | Aggregation surface (endpoint) | `apps/api/routes/internal.py` → `GET /internal/ops/snapshot` | System state in one call — total, actionable, claimed, pending, urgent |
| Follow-up Handoffs | Endpoint | `apps/api/routes/internal.py` → `GET /internal/followup-handoffs` | Human-readable retry action handoff for no_answer leads |
| Follow-up Automation | Endpoint | `apps/api/routes/internal.py` → `GET /internal/followup-automation` | Machine-consumable follow-up payloads with nested payload structure |
| Follow-up CSV Export | Endpoint | `apps/api/routes/internal.py` → `GET /internal/followup-automation/export.csv` | CSV export of followup items for manual operator email workflow |
| Source Intelligence (unified) | Endpoint | `apps/api/routes/internal.py` → `GET /internal/source-intelligence` | Unified per-source view: leads, score, actions, outcomes, recommendation. Optional source filter |
| `_get_actionable_leads()` | Private helper (acts as shared construct) | `apps/api/routes/leads.py` | Single source of actionable lead selection — used by 10+ internal surfaces |
| `_get_claimed_lead_ids()` | Private helper (acts as shared construct) | `apps/api/routes/internal.py` | Claimed lead exclusion set — used by 8+ internal surfaces |
| `emit_event()` | Helper function | `apps/api/events.py` | Best-effort event emission — silent on failure, never blocks caller |

---

## Major Modules

| Module | Primary path | Status | What it is |
|--------|-------------|--------|------------|
| **Leads core** | `apps/api/routes/leads.py` | Active (frozen D7) | Lead CRUD, ingestion, packs, export, operational summaries |
| **Internal ops** | `apps/api/routes/internal.py` | Active | Queue, dispatch, claims, review, handoffs, outcomes, follow-up, daily actions, bots |
| **Services** | `apps/api/services/` | Active | Scoring (`scoring.py`), actions (`actions.py`), lead pack (`leadpack.py`) |
| **Internal Event Spine** | `apps/api/events.py` | Active | Append-only event log, best-effort, `emit_event()` helper |
| **Automation bridge** | `apps/api/automations/followup_bridge.py` | Active (tested in-repo; not yet integrated with external consumers) | Consumer bridge for `/internal/followup-automation` → execution-ready output |
| **Core (shared primitives)** | `core/` | Stub | Reserved for cross-module primitives. No code exists. |

---

## Lead Entry Paths

All flow through `_create_lead_internal()` in `apps/api/routes/leads.py`.

| Path | Endpoint | Source convention | Notes |
|------|----------|-------------------|-------|
| Direct | `POST /leads` | Any | Legacy-compatible, no source format validation |
| Bulk ingest | `POST /leads/ingest` | Any | Batch of `LeadCreate`, returns counts |
| Webhook single | `POST /leads/webhook/{provider}` | `webhook:{provider}` | Provider validated with regex |
| Webhook batch | `POST /leads/webhook/{provider}/batch` | `webhook:{provider}` | Same as single, iterated |
| External adapter | `POST /leads/external` | Canonical `type:id` | Phone/metadata via `@ext:` in notes. Source format enforced |

---

## Internal Endpoints by Purpose

### Operational queues (read-only projections, no persistence)
| Endpoint | What it answers |
|----------|----------------|
| `GET /internal/queue` | "What needs attention next?" — flat prioritized list |
| `GET /internal/dispatch` | "What's ready for automation?" — with embedded lead packs |
| `GET /internal/review` | "What needs human review?" — send_to_client + review_manually |
| `GET /internal/client-ready` | "What's ready for the client?" — send_to_client only |
| `GET /internal/worklist` | "Show me everything in one call" — pending + client-ready + recently claimed |
| `GET /internal/daily-actions` | "What should we do today?" — review + client-ready + followup + source warnings, capped |

### Claims (stateful)
| Endpoint | What it does |
|----------|-------------|
| `POST /internal/dispatch/claim` | Claim leads for processing |
| `DELETE /internal/dispatch/claim/{lead_id}` | Release a claim |
| `POST /internal/review/{lead_id}/claim` | Claim a reviewable lead |

### Handoffs & follow-up
| Endpoint | What it answers |
|----------|----------------|
| `GET /internal/handoffs` | "What goes outbound?" — channel + instruction per lead |
| `GET /internal/handoffs/export.csv` | Same as handoffs, CSV format |
| `GET /internal/followup-queue` | "Who didn't answer?" — no_answer leads, score-sorted |
| `GET /internal/followup-handoffs` | "What retry action for each?" — human-readable handoff |
| `GET /internal/followup-automation` | "Machine-consumable retry payloads" — designed for n8n/bridge consumption |
| `GET /internal/followup-automation/export.csv` | "Operator CSV for manual followup" — download, copy to/subject/body, send |

### Outcomes
| Endpoint | What it does |
|----------|-------------|
| `POST /internal/outcomes` | Record/upsert real-world outcome (6 allowed values) |
| `GET /internal/outcomes/summary` | Aggregate outcome counts |
| `GET /internal/outcomes/by-source` | Outcome counts by source |

### Source intelligence
| Endpoint | What it answers |
|----------|----------------|
| `GET /internal/source-performance` | "How is each source performing?" — totals, avg score, quality |
| `GET /internal/source-actions` | "What should we do about each source?" — keep/review heuristic |
| `GET /internal/source-outcome-actions` | "What do real outcomes say about each source?" — 5 rules, outcome-aware |
| `GET /internal/source-intelligence` | "Everything about each source in one call" — unified view with totals, outcomes, recommendation |

### Ops snapshot
| Endpoint | What it answers |
|----------|----------------|
| `GET /internal/ops/snapshot` | "System state in one call" — total, actionable, claimed, pending, urgent |

### Event log
| Endpoint | What it does |
|----------|-------------|
| `GET /internal/events` | Read recent events (newest first, filterable by event_type) |

### Quality bots (read-only, deterministic, no side effects)
| Bot | Endpoint | What it checks |
|-----|----------|----------------|
| **Sentinel** | `GET /internal/sentinel` | Operational health: stale claims, source attention, event spine silence |
| **Audit** | `GET /internal/audit` | Cross-module consistency: source surface agreement, ops snapshot arithmetic |
| **Redundancy** | `GET /internal/redundancy` | Project weight: absorbed skills, dormant stubs, CLAUDE.md duplication |
| **Scope Critic** | `POST /internal/scope-critic` | Pre-build review: file spread, missing scope, risk acknowledgment |
| **Proof Verifier** | `POST /internal/proof-verifier` | Post-build closure review: claimed vs actual, evidence quality |
| **Drift Detector** | `POST /internal/drift-detector` | Plan-vs-execution cross-reference: file addition/omission drift, classification drift, out-of-scope intrusion. Advisory only. |

---

## Internal Event Spine

| Aspect | Detail |
|--------|--------|
| **Module** | `apps/api/events.py` |
| **Function** | `emit_event(event_type, entity_type, entity_id, origin_module, payload)` |
| **Storage** | `events` table (SQLite, append-only) |
| **Model** | Best-effort — `except Exception: pass`. Never blocks primary operations. |
| **Contract** | `docs/operational_contracts.md` → "Internal Event Spine" + "Current Event Types" |

### Current event types
| Event | Origin | Payload | Emitted by |
|-------|--------|---------|------------|
| `lead.created` | `leads` | `{source, score}` | `_create_lead_internal()` in `leads.py` |
| `lead.claimed` | `dispatch` | `{}` | `claim_dispatch_items()` in `internal.py` |
| `lead.claimed` | `review` | `{}` | `claim_review_lead()` in `internal.py` |
| `lead.released` | `dispatch` | `{}` | `release_claim()` in `internal.py` |
| `lead.outcome_recorded` | `outcomes` | `{outcome}` | `post_outcome()` in `internal.py` |

### Who reads events
- `GET /internal/events` — direct listing
- Sentinel `_check_event_spine_silent` — checks for total silence and recent silence (24h window)
- Audit — does **not** use events (deliberately deferred; best-effort makes event audits structurally weak)

---

## Shared Constructs & Reused Helpers

| Name | Location | Used by |
|------|----------|---------|
| `_create_lead_internal()` | `leads.py` | All 5 lead entry paths |
| `_get_actionable_leads()` | `leads.py` | actionable, worklist, queue, dispatch, review, client-ready, handoffs, daily-actions, followup-handoffs, followup-automation, sentinel, audit, ops/snapshot |
| `_get_claimed_lead_ids()` | `internal.py` | dispatch, review, client-ready, handoffs, followup-queue, followup-handoffs, followup-automation, daily-actions |
| `get_lead_pack()` | `leads.py` | pack, html, text, delivery, operational, dispatch items, followup-queue |
| `get_rating()` | `leadpack.py` | All surfaces showing rating; followup-handoffs, followup-automation |
| `determine_next_action()` | `actions.py` | `_get_actionable_leads()`, operational summaries |
| `should_alert()` | `actions.py` | `_get_actionable_leads()`, queue, dispatch sorting |
| `get_instruction()` | `actions.py` | `LeadOperationalSummary` enrichment |
| `emit_event()` | `events.py` | lead creation, claim, release, outcome recording |
| `ACTION_PRIORITY` | `actions.py` | Queue, dispatch, handoff sorting |

---

## Key Scoring & Decision Rules

| Rule | Thresholds | Location |
|------|-----------|----------|
| Score calculation | base 50, +10 user notes, cap 100 | `services/scoring.py` |
| Rating | low <50, medium 50–74, high >=75 | `services/leadpack.py` → `get_rating()` |
| next_action | >=60 send_to_client, 40–59 review/request, <40 enrich/discard | `services/actions.py` |
| Alert | score >= 60 | `services/actions.py` → `should_alert()` |
| Dedup | UNIQUE(email, source), both normalized lowercase+strip | `leads.py` + DB constraint |

---

## Database Tables

| Table | Purpose | Key constraints |
|-------|---------|-----------------|
| `leads` | Core lead storage | PK: id. UNIQUE(email, source) |
| `dispatch_claims` | Claim tracking | lead_id UNIQUE |
| `events` | Append-only event log | INDEX on event_type |
| `lead_outcomes` | Real-world outcomes | PK: lead_id REFERENCES leads(id). 6 allowed values |

Schema defined in `apps/api/db.py` → `init_db()`.

---

## Documentation Map

| Doc | What it owns | Authority level |
|-----|-------------|-----------------|
| `docs/operational_contracts.md` | Endpoint contracts, event spine contract, sentinel/audit/redundancy checks, bot rules | **Primary** — source of truth for all operational behavior |
| `docs/leads_runbook.md` | Leads module operational procedures | **Primary** for leads ops |
| `docs/leads_decision_log.md` | Frozen decisions (D1–D22), provisional assumptions (P1–P3), known divergences, follow-ups (F1–F13) | **Primary** for what is settled and what is deferred |
| `docs/00_project_context_master.md` | Business context, vertical strategy, rules 1–36 | **Primary** for product direction and constraints |
| `docs/integration/n8n_interface.md` | n8n polling interface, stable field contracts | **Primary** for external integration design (n8n integration is documented but not yet deployed) |
| `docs/execution_protocol.md` | BUILD/HARDEN execution discipline | **Active** governance |
| `docs/work_templates.md` | BUILD/HARDEN block templates (quick + elite) | **Active** governance |
| `docs/CLAUDE.md` | Documentation truthfulness rules | **Active** governance |
| `.claude/CLAUDE.md` | Global operating rules (14 sections) | **Constitutional** — highest authority |
| `apps/api/CLAUDE.md` | API module local rules, review flow, risk classes | **Active** local governance |
| `apps/api/routes/CLAUDE.md` | Route/contract editing rules | **Active** local governance |
| `apps/api/automations/CLAUDE.md` | Bridge module rules (no business logic, no persistence) | **Active** local governance |

---

## Active vs Stub/Deferred Areas

### Active (code exists, tested, maintained)
- Leads core (frozen D7 — bugs/regressions only)
- All internal endpoints
- Services (scoring, actions, leadpack)
- Event spine
- Followup bridge (tested in-repo; no external consumers yet)
- All quality bots (sentinel, audit, redundancy, scope-critic, proof-verifier, drift-detector)
- Full test suite (495 tests)

### Static site (Sentyacht web)
- `static/site/` — Sentyacht corporate home (`index.html`) + seller landing (`vender/index.html`) + CSS (`css/`)
- Landing form submits to `POST /api/leads/webhook/landing-barcos-venta`

### Stub (placeholder only, no code)
- `core/` — shared cross-module primitives (CLAUDE.md stub exists)
- `scripts/` — empty

### Deferred (documented, not built)
- Real scoring engine (F7)
- Threshold/label alignment with context master (F1, D1)
- Full attribution model (F2)
- Lead lifecycle states (F5, V3)
- Event-based audit checks (operational_contracts.md:292)
- Source registry/whitelist (D18 triggers)
- Batch for `/leads/external` (F12)

---

## Where to Look When You Need...

| You need... | Go to... |
|-------------|----------|
| What an endpoint returns | `docs/operational_contracts.md` |
| Why a decision was made | `docs/leads_decision_log.md` |
| How scoring/rating/actions work | `apps/api/services/` (scoring.py, actions.py, leadpack.py) |
| What events are emitted | `apps/api/events.py` + `docs/operational_contracts.md` → "Current Event Types" |
| What the sentinel checks | `apps/api/routes/internal.py` → `_check_*` functions |
| What the audit checks | `apps/api/routes/internal.py` → `_audit_*` functions |
| How leads are created internally | `apps/api/routes/leads.py` → `_create_lead_internal()` |
| What shared helpers exist | This file → "Shared Constructs & Reused Helpers" |
| How n8n consumes the API | `docs/integration/n8n_interface.md` |
| What the bridge does | `apps/api/automations/followup_bridge.py` + `apps/api/automations/CLAUDE.md` |
| What skills exist | `skills/` directory — see `docs/component_index.md` for classification |
| What is frozen vs deferred | `docs/leads_decision_log.md` (D-numbers = frozen, F-numbers = deferred) |
| DB schema | `apps/api/db.py` → `init_db()` |
| All Pydantic models | `apps/api/schemas.py` |
| How to run tests | `python -m pytest tests/ -v` |
| What is protected from editing | `.claude/CLAUDE.md` §10 — approval boundaries |

---

## Confusing Names / Discoverability Traps

Things that are hard to find or easy to confuse in this repo:

| Trap | Why it's confusing | Truth |
|------|-------------------|-------|
| **Internal Event Spine** lives in `events.py` | The name "Internal Event Spine" appears in docs and comments, but the file is just `events.py` — no directory, no module name signals its cross-module role | Search for "event spine" or "emit_event" to find it |
| **`_get_actionable_leads()`** is private | The most reused helper in the system (10+ consumers) is a private function inside a route file, not a service | Lives in `apps/api/routes/leads.py`, not in `services/` |
| **All bots are inline in `internal.py`** | Sentinel, audit, redundancy, scope-critic, and proof-verifier are all defined inline in a 1800+ line file. No separate bot module | Search for `_check_*` (sentinel), `_audit_*` (audit), `_check_*_redundant` (redundancy) |
| **`source-actions` vs `source-outcome-actions`** | Two endpoints with similar names, very different signal sources | `source-actions` = proxy heuristics over performance metrics. `source-outcome-actions` = real recorded outcomes with 5 deterministic rules |
| **`core/` exists but is empty** | A developer browsing the repo would expect shared code there | It's a stub. The CLAUDE.md inside says "Not yet implemented. No code exists here." |
| **Follow-up has 3 surfaces** | "follow-up" could mean the queue, the handoffs, or the automation endpoint | `followup-queue` = who. `followup-handoffs` = human action. `followup-automation` = machine payload |
| **Bridge is colocated under `apps/api/`** | The followup bridge lives at `apps/api/automations/` despite not being API business logic | Placement is for MVP pragmatism. `automations/CLAUDE.md` documents that it should move to `workers/` or `bridges/` if more consumers appear |

---

## Maintenance Rule

This map must be updated when:
- A new module, endpoint group, or shared construct is added
- A stub becomes active or an active area is frozen/deprecated
- A new event type is added to the spine
- A new bot or sentinel check is added
- The doc authority hierarchy changes

Do not update this map for: individual endpoint tweaks, test additions, doc wording fixes, or within-module refactors. Those belong in `operational_contracts.md`.
