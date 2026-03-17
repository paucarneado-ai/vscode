# Component Index

> Structured registry of named components in the OpenClaw repo.
> For high-level navigation, see `docs/system_map.md`.
> For endpoint contracts, see `docs/operational_contracts.md`.

---

## Leads Core

**Type:** Module (routes + services)
**Status:** Active — frozen (D7), bugs/regressions only
**Primary path:** `apps/api/routes/leads.py`
**Purpose:** Lead CRUD, all ingestion paths, packs, export, operational summaries
**Depends on:** `db.py`, `schemas.py`, `services/scoring.py`, `services/actions.py`, `services/leadpack.py`, `events.py`
**Used by:** Internal ops (`internal.py` imports `_get_actionable_leads`, `get_lead_pack`)
**Source of truth:** `docs/leads_runbook.md`, `docs/leads_decision_log.md`
**Key tests:** `tests/api/test_api.py` — lead CRUD, packs, ingest, webhook, external, export, dedup
**Notes:** `_create_lead_internal()` is the single creation path for all 5 entry points. `_get_actionable_leads()` is the most reused helper in the system.

---

## Scoring Service

**Type:** Service
**Status:** Active — placeholder (P2, F7)
**Primary path:** `apps/api/services/scoring.py`
**Purpose:** `calculate_lead_score(source, notes)` — base 50, +10 user notes (non-`@ext:`), cap 100
**Depends on:** Nothing external
**Used by:** `_create_lead_internal()` in `leads.py`
**Source of truth:** Decision log P2, D19
**Key tests:** `test_api.py` — scoring tests, `@ext:` handling, `_has_user_notes()` unit tests
**Notes:** Placeholder functional scoring. Not commercial logic. `_has_user_notes()` distinguishes real notes from `@ext:` metadata.

---

## Actions Service

**Type:** Service
**Status:** Active
**Primary path:** `apps/api/services/actions.py`
**Purpose:** `determine_next_action()`, `should_alert()`, `get_instruction()`, `ACTION_PRIORITY`
**Depends on:** `services/scoring.py` (`_has_user_notes`)
**Used by:** `_get_actionable_leads()`, all queue/dispatch/review surfaces
**Source of truth:** Decision log D3, D4, D13
**Key tests:** `test_api.py` — action determination, instruction mapping, `@ext:` handling, ACTION_PRIORITY import
**Notes:** 5 action values: send_to_client, review_manually, request_more_info, enrich_first, discard. Alert threshold: score >= 60.

---

## Lead Pack Service

**Type:** Service
**Status:** Active
**Primary path:** `apps/api/services/leadpack.py`
**Purpose:** `get_rating()`, `build_summary()`, `render_lead_pack_html()`, `render_lead_pack_text()`
**Depends on:** Nothing external
**Used by:** Pack endpoints, operational summaries, followup-handoffs, followup-automation
**Source of truth:** Decision log P3
**Key tests:** `test_api.py` — pack rendering, rating thresholds
**Notes:** Rating thresholds: low <50, medium 50–74, high >=75. Diverges from context master (V1) — accepted.

---

## Internal Event Spine

**Type:** Shared cross-module construct
**Status:** Active
**Primary path:** `apps/api/events.py`
**Purpose:** Append-only event log for operational traceability. `emit_event()` helper with best-effort semantics.
**Depends on:** `db.py` (`get_db`)
**Used by:** `leads.py` (lead.created), `internal.py` (lead.claimed, lead.released, lead.outcome_recorded), sentinel (`_check_event_spine_silent`)
**Source of truth:** `docs/operational_contracts.md` → "Internal Event Spine" + "Current Event Types"
**Key tests:** `test_api.py` — `test_event_emitted_on_*`, `test_events_*`, `test_event_emission_failure_*`, `test_sentinel_event_spine_*`
**Notes:** 5 event types from 4 origin modules. Silent failure model (`except Exception: pass`). No subscribers, no handlers, no retry. Storage: `events` table.

---

## Dispatch & Claims

**Type:** Endpoint group (stateful)
**Status:** Active
**Primary path:** `apps/api/routes/internal.py`
**Purpose:** Queue, dispatch, claim/release lifecycle for async lead processing
**Depends on:** `_get_actionable_leads()`, `_get_claimed_lead_ids()`, `get_lead_pack()`, `events.py`
**Used by:** Sentinel (stale_claims check), audit (ops_snapshot_arithmetic), review, handoffs, daily-actions
**Source of truth:** `docs/operational_contracts.md` → dispatch/claim sections
**Key tests:** `test_api.py` — queue, dispatch, claim, release, already_claimed, not_found, stale claims
**Notes:** Claims persist in `dispatch_claims` table until released. UNIQUE(lead_id). Emits `lead.claimed`/`lead.released` events.

---

## Review & Client-Ready

**Type:** Endpoint group (read-only + claim)
**Status:** Active
**Primary path:** `apps/api/routes/internal.py`
**Purpose:** Human review queue, client-ready filtering, review-specific claiming
**Depends on:** `_get_actionable_leads()`, `_get_claimed_lead_ids()`
**Used by:** Worklist, daily-actions
**Source of truth:** `docs/operational_contracts.md` → review/client-ready sections
**Key tests:** `test_api.py` — review shape, reviewability validation, review claim
**Notes:** Review claim emits `lead.claimed` with `origin_module=review`.

---

## Outcomes

**Type:** Endpoint group (stateful)
**Status:** Active
**Primary path:** `apps/api/routes/internal.py`
**Purpose:** Record real-world outcomes, outcome summaries, outcome-by-source
**Depends on:** `db.py` (lead_outcomes table), `events.py`
**Used by:** followup-queue, followup-handoffs, followup-automation, source-outcome-actions, daily-actions
**Source of truth:** `docs/operational_contracts.md` → outcomes sections
**Key tests:** `test_api.py` — outcome recording, upsert, summary, by-source, event emission
**Notes:** 6 values: contacted, qualified, won, lost, no_answer, bad_fit. Upsert via `ON CONFLICT DO UPDATE`. Emits `lead.outcome_recorded`.

---

## Follow-up Surfaces

**Type:** Endpoint group (read-only)
**Status:** Active
**Primary path:** `apps/api/routes/internal.py`
**Purpose:** Retry action surfaces for no_answer leads

| Surface | Endpoint | Audience |
|---------|----------|----------|
| Queue | `GET /internal/followup-queue` | Operator — who didn't answer |
| Handoffs | `GET /internal/followup-handoffs` | Human — action + instruction + message |
| Automation | `GET /internal/followup-automation` | Machine — nested payload designed for n8n (not yet consumed externally) |
| CSV Export | `GET /internal/followup-automation/export.csv` | Operator — downloadable CSV for manual email workflow. Columns: lead_id, to, subject, body, channel, priority, source, score, rating |

**Depends on:** `_get_actionable_leads()`, `_get_claimed_lead_ids()`, `get_lead_pack()`, `get_rating()`
**Used by:** Followup bridge, daily-actions
**Source of truth:** `docs/operational_contracts.md` → followup sections
**Key tests:** `test_api.py` — shape, fields, exclusions, rating, ordering, determinism
**Notes:** Helpers `_followup_instruction(rating)` and `_followup_message(name, rating)` in `internal.py`.

---

## Followup Bridge

**Type:** Consumer bridge module
**Status:** Active (tested in-repo; not yet integrated with external consumers)
**Primary path:** `apps/api/automations/followup_bridge.py`
**Purpose:** Consume `GET /internal/followup-automation`, map to execution-ready `BridgeItem` objects
**Depends on:** Any HTTP-like client with `.get(path)` interface
**Used by:** Designed for external consumers (n8n); not yet integrated externally. Not called by the API itself.
**Source of truth:** `apps/api/automations/CLAUDE.md`, `docs/operational_contracts.md` → bridge section
**Key tests:** `tests/automations/test_followup_bridge.py` — 11 tests
**Notes:** Does NOT send, schedule, persist, re-order, re-score, or add business logic. Deterministic subject mapping by rating. Partial failure: invalid items skipped with error recorded. `total_fetched` = API-declared total, not `len(items)`.

---

## Source Intelligence

**Type:** Endpoint group (read-only)
**Status:** Active
**Primary path:** `apps/api/routes/internal.py`

| Surface | Endpoint | Signal source |
|---------|----------|---------------|
| Performance | `GET /internal/source-performance` | Lead counts, avg score, quality metrics |
| Actions (proxy) | `GET /internal/source-actions` | Heuristics over performance data |
| Actions (outcome) | `GET /internal/source-outcome-actions` | Real recorded outcomes, 5 deterministic rules |
| Intelligence (unified) | `GET /internal/source-intelligence` | All-in-one per-source view: leads, score, actions, outcomes, recommendation. Optional `source` filter |

**Depends on:** `_get_actionable_leads()`, lead_outcomes table
**Used by:** Sentinel (source_needs_attention), audit (source_surface_consistency), daily-actions
**Source of truth:** `docs/operational_contracts.md`
**Key tests:** `test_api.py` — source performance, source actions, source outcome actions
**Notes:** `_source_outcome_recommendation()` has 5 rules with `_OUTCOME_MIN_DATA = 3` threshold.

---

## Sentinel Bot

**Type:** Quality bot (read-only, deterministic)
**Status:** Active
**Primary path:** `apps/api/routes/internal.py` → `GET /internal/sentinel`
**Purpose:** Operational health checks. Returns status (ok/watch/alert) and findings.

| Check | Surface | What it detects |
|-------|---------|-----------------|
| `stale_claims` | dispatch | Claims older than 24h |
| `source_needs_attention` | source-actions | Sources flagged for review |
| `event_spine_silent` | events | Total silence (high) or recent silence with 24h window (medium) |

**Depends on:** `_get_actionable_leads()`, `_get_claimed_lead_ids()`, events table, dispatch_claims table
**Used by:** Nothing automated (consumed by operator manually; n8n polling designed but not yet deployed)
**Source of truth:** `docs/operational_contracts.md` → "Sentinel Checks"
**Key tests:** `test_api.py` — shape, severity derivation, stale claims, event spine silence, recent silence, determinism

---

## Audit Bot

**Type:** Quality bot (read-only, deterministic)
**Status:** Active
**Primary path:** `apps/api/routes/internal.py` → `GET /internal/audit`
**Purpose:** Cross-module consistency checks. Returns status (pass/warn/fail) and findings.

| Check | Surface | What it detects |
|-------|---------|-----------------|
| `source_surface_consistency` | source-performance / source-actions | Source list/totals disagreement |
| `ops_snapshot_arithmetic` | ops/snapshot | pending_dispatch != actionable - claimed |

**Depends on:** `_get_actionable_leads()`, `_get_claimed_lead_ids()`, leads table
**Used by:** Nothing (consumed by operator)
**Source of truth:** `docs/operational_contracts.md` → "Audit Checks"
**Key tests:** `test_api.py` — shape, status derivation, arithmetic check
**Notes:** Deliberately ignores events (best-effort emission makes event audits structurally weak — documented debt at operational_contracts.md:292).

---

## Redundancy Bot

**Type:** Quality bot (filesystem-only, deterministic)
**Status:** Active
**Primary path:** `apps/api/routes/internal.py` → `GET /internal/redundancy`
**Purpose:** Detect redundant skills, dormant stubs, CLAUDE.md duplication
**Depends on:** Filesystem scan of `skills/` and `**/CLAUDE.md`
**Used by:** Nothing (consumed by operator)
**Source of truth:** `docs/operational_contracts.md` → "Redundancy Checks"
**Key tests:** `test_api.py` — shape, candidate detection, dormant stubs, literal duplication
**Notes:** Hardcoded candidate list for skill redundancy. Does not touch database or events.

---

## Scope Critic

**Type:** Governance bot (stateless, deterministic)
**Status:** Active
**Primary path:** `apps/api/routes/internal.py` → `POST /internal/scope-critic`
**Purpose:** Pre-build structural review of BUILD/HARDEN proposals
**Depends on:** Nothing (pure input analysis)
**Used by:** YELLOW/RED blocks per `apps/api/CLAUDE.md` review flow
**Source of truth:** `docs/operational_contracts.md` → "Scope Critic"
**Key tests:** `test_api.py` — shape, check detection, status derivation

---

## Proof Verifier

**Type:** Governance bot (stateless, deterministic)
**Status:** Active
**Primary path:** `apps/api/routes/internal.py` → `POST /internal/proof-verifier`
**Purpose:** Post-build closure review of completion reports
**Depends on:** Nothing (pure input analysis)
**Used by:** YELLOW/RED block closure per `apps/api/CLAUDE.md` review flow
**Source of truth:** `docs/operational_contracts.md` → "Proof Verifier"
**Key tests:** `test_api.py` — shape, blocks_closure flag, status derivation

---

## Drift Detector

**Type:** Governance bot (stateless, deterministic, advisory-only)
**Status:** Active (not yet integrated into REVIEW FLOW constitution)
**Primary path:** `apps/api/routes/internal.py` → `POST /internal/drift-detector`
**Purpose:** Plan-vs-execution cross-reference — compares Scope Critic input against Proof Verifier report to detect drift
**Depends on:** Nothing (pure input analysis)
**Used by:** Nothing automated (manual invocation only; not yet in REVIEW FLOW)
**Source of truth:** `docs/operational_contracts.md` → "Drift Detector"
**Key tests:** `test_api.py` — shape, clean alignment, file addition/omission drift, classification drift, out-of-scope intrusion, no false positives, path normalization, determinism
**Notes:** 4 checks: file_addition_drift (high), file_omission_drift (medium), classification_drift (medium), out_of_scope_intrusion (high). Advisory only — no `blocks_closure` equivalent. Conservative exact matching for out-of-scope intrusion (no substring/fuzzy).

---

## Daily Actions

**Type:** Composition surface (read-only)
**Status:** Active
**Primary path:** `apps/api/routes/internal.py` → `GET /internal/daily-actions`
**Purpose:** "What should we do today?" — review + client-ready + followup + source warnings in one call
**Depends on:** `_get_actionable_leads()`, `_get_claimed_lead_ids()`, outcomes, source-outcome-actions
**Used by:** Nothing automated (consumed by operator manually; n8n polling designed but not yet deployed)
**Source of truth:** `docs/operational_contracts.md`
**Key tests:** `test_api.py` — shape, section caps (`_DAILY_CAP = 5`), exclusions, determinism
**Notes:** Capped at 5 items per section. Summary counts reflect full uncapped set.

---

## Ops Snapshot

**Type:** Aggregation surface (read-only)
**Status:** Active
**Primary path:** `apps/api/routes/internal.py` → `GET /internal/ops/snapshot`
**Purpose:** System state in one call — total, actionable, claimed, pending, urgent
**Depends on:** `_get_actionable_leads()`, `_get_claimed_lead_ids()`
**Used by:** Audit (ops_snapshot_arithmetic check)
**Source of truth:** `docs/operational_contracts.md`
**Key tests:** `test_api.py` — shape, arithmetic consistency

---

## Demo Intake

**Type:** Demo-only HTML surface
**Status:** Active (hardened)
**Primary path:** `apps/api/routes/demo.py` → `GET /demo/intake`
**Purpose:** Internal demo form for lead submission
**Depends on:** Nothing (self-contained HTML)
**Used by:** Nothing (human-facing demo only)
**Source of truth:** `docs/operational_contracts.md`
**Key tests:** `test_api.py` — `test_demo_intake_defensive_markers` (noindex, no-store, nosniff, visible copy)
**Notes:** Not a production surface. Protected with anti-indexing, anti-caching, MIME-sniffing headers, and visible "Internal demo only" footer.

---

## Skills (Governance)

### Architecture/quality skills (`skills/`)
| Skill | Status | Absorbed by global CLAUDE.md? |
|-------|--------|-------------------------------|
| `architecture_guardian` | Active | Partially (redundancy bot candidate) |
| `auto_test_generator` | Active | No |
| `clean_code_enforcer` | Active | Partially (redundancy bot candidate) |
| `complexity_killer` | Active | No |
| `dependency_risk_guard` | Active | No |
| `human_approval_guard` | Active | Partially (redundancy bot candidate) |
| `integration_test_builder` | Active | No |
| `regression_sentinel` | Active | No |
| `safe_scaffolder` | Active | No |
| `schema_contract_guard` | Active | No |
| `task_decomposer` | Active | No |
| `type_safety_guard` | Active | No |

### Operational skills (`skills/operational/`)
| Skill | Status | Purpose |
|-------|--------|---------|
| `automation-consumer-guard` | Active | Guards bridge modules against scope creep |
| `autoresearch-lite` | Active | Fast codebase research |
| `block-executor` | Active | Executes work blocks with traceability |
| `decision-log-updater` | Active | Updates decision log |
| `integration-safety` | Active | Guards integration compatibility |
| `sandbox-gate` | Active | Gates experimental work |
| `scope-guard` | Active | Guards scope boundaries |
| `skill-builder-openclaw` | Active | Meta-skill for building skills |

---

## Stub / Deferred Components

| Component | Path | Why deferred |
|-----------|------|-------------|
| Core shared primitives | `core/` | No cross-module code has proven stable enough to promote |
| Real scoring engine | — | F7: requires commercial signal design per vertical |
| Lead lifecycle states | — | F5, V3: not needed for MVP |
| Full attribution model | — | F2: source is sufficient for MVP |
| Event-based audit checks | — | Best-effort emission makes them structurally weak |
| Source registry/whitelist | — | D18: triggers defined but not yet hit |

---

## Maintenance Rule

Update this index when:
- A component is added, renamed, promoted from stub, or deprecated
- A component's dependencies or consumers change materially
- A new bot, service, or shared construct is introduced

Do not update for: endpoint parameter tweaks, test additions, doc wording, or internal refactors within a component.
