# Pathway Audit Report — 2026-03-18 20:44

## Summary
- Modules: 17 | Functions: 52 | Traces: 56 | Pathways: 66
- Candidates: 7 (immediate=0, debt=0, backlog=7, watchlist=0, ignored=0)

## Delta vs Previous Audit
- candidates: 7 (unchanged)
- known_debt: 0 (unchanged)
- backlog: 7 (unchanged)
- watchlist: 0 (unchanged)
- prohibited_new: 0 (unchanged)
- max_fan_out_runtime: 9 (unchanged)
- max_fan_in: 9 (unchanged)

## Module Drift
No notable module drift detected.

## Immediate Review
None.

## Known Debt
None.

## Backlog
### PR-001: redundant_transform
- **Score:** 68.5 | **Priority:** medium | **Governance:** RECOMMENDED_FOR_AUTO_APPROVAL
- **Confidence:** 0.95 — avg confidence 0.95 across 3 traces
- **Occurrences:** 3
- **Description:** apps.api.services.operational._get_actionable_leads called from 3 distinct functions
- **Modules:** apps.api.routes.internal, apps.api.routes.leads, apps.api.services.operational
- **Impact:** local | **Effort:** small | **Risk:** low
- **Action:** extract_shared_function
- **Evidence** (3 sites):
  - `apps/api/routes/internal.py:28 get_internal_queue() -> _get_actionable_leads()`
  - `apps/api/routes/leads.py:165 get_actionable_leads() -> _get_actionable_leads()`
  - `apps/api/routes/leads.py:173 get_actionable_worklist() -> _get_actionable_leads()`

### PR-002: redundant_transform
- **Score:** 64.8 | **Priority:** medium | **Governance:** RECOMMENDED_FOR_AUTO_APPROVAL
- **Confidence:** 0.95 — avg confidence 0.95 across 5 traces
- **Occurrences:** 5
- **Description:** apps.api.services.intake._create_lead_internal called from 5 distinct functions
- **Modules:** apps.api.routes.leads, apps.api.services.intake
- **Impact:** local | **Effort:** small | **Risk:** low
- **Action:** extract_shared_function
- **Evidence** (5 sites):
  - `apps/api/routes/leads.py:49 create_lead() -> _create_lead_internal()`
  - `apps/api/routes/leads.py:65 ingest_leads() -> _create_lead_internal()`
  - `apps/api/routes/leads.py:84 web_intake() -> _create_lead_internal()`
  - `apps/api/routes/leads.py:99 webhook_ingest() -> _create_lead_internal()`
  - `apps/api/routes/leads.py:124 webhook_ingest_batch() -> _create_lead_internal()`

### PR-003: long_path
- **Score:** 57.0 | **Priority:** medium | **Governance:** NEEDS_HUMAN
- **Confidence:** 0.75 (raw=0.95, penalty=-0.2) — base=0.95 from 1+2 traces; penalty=-0.2 (fan-out=6 suggests orchestrator; calls 4 distinct downstream modules)
- **Occurrences:** 1
- **Intermediate role:** shared_composer (conf=0.7) -- calls 4 external modules; invokes 8 distinct functions including composition
- **Description:** Chain apps.api.routes.internal -> apps.api.services.operational -> apps.api.db: operational is a shared composition hub; persistent structural pattern, not confirmed pass-through (orchestrator signals: fan-out=6 suggests orchestrator; calls 4 distinct downstream modules)
- **Modules:** apps.api.routes.internal, apps.api.services.operational, apps.api.db
- **Impact:** structural | **Effort:** medium | **Risk:** low
- **Action:** evaluate_direct_path
- **Evidence** (3 sites):
  - `apps/api/routes/internal.py:28 get_internal_queue->_get_actionable_leads`
  - `apps/api/services/operational.py:42 get_actionable_leads->get_db`
  - `apps/api/services/operational.py:80 get_lead_pack_by_id->get_db`

### PR-004: long_path
- **Score:** 57.0 | **Priority:** medium | **Governance:** NEEDS_HUMAN
- **Confidence:** 0.75 (raw=0.95, penalty=-0.2) — base=0.95 from 1+4 traces; penalty=-0.2 (fan-out=6 suggests orchestrator; calls 4 distinct downstream modules)
- **Occurrences:** 1
- **Intermediate role:** shared_composer (conf=0.7) -- calls 4 external modules; invokes 8 distinct functions including composition
- **Description:** Chain apps.api.routes.internal -> apps.api.services.operational -> apps.api.services.leadpack: operational is a shared composition hub; persistent structural pattern, not confirmed pass-through (orchestrator signals: fan-out=6 suggests orchestrator; calls 4 distinct downstream modules)
- **Modules:** apps.api.routes.internal, apps.api.services.operational, apps.api.services.leadpack
- **Impact:** structural | **Effort:** medium | **Risk:** low
- **Action:** evaluate_direct_path
- **Evidence** (3 sites):
  - `apps/api/routes/internal.py:28 get_internal_queue->_get_actionable_leads`
  - `apps/api/services/operational.py:17 build_operational_summary->get_rating`
  - `apps/api/services/operational.py:28 build_operational_summary->build_summary`

### PR-006: long_path
- **Score:** 57.0 | **Priority:** medium | **Governance:** NEEDS_HUMAN
- **Confidence:** 0.75 (raw=0.95, penalty=-0.2) — base=0.95 from 13+5 traces; penalty=-0.2 (fan-out=5 suggests orchestrator; calls 3 distinct downstream modules)
- **Occurrences:** 1
- **Intermediate role:** shared_composer (conf=0.7) -- calls 3 external modules; invokes 5 distinct functions including composition
- **Description:** Chain apps.api.routes.leads -> apps.api.services.intake -> apps.api.db: intake is a shared composition hub; persistent structural pattern, not confirmed pass-through (orchestrator signals: fan-out=5 suggests orchestrator; calls 3 distinct downstream modules)
- **Modules:** apps.api.routes.leads, apps.api.services.intake, apps.api.db
- **Impact:** structural | **Effort:** medium | **Risk:** low
- **Action:** evaluate_direct_path
- **Evidence** (4 sites):
  - `apps/api/routes/leads.py:49 create_lead->_create_lead_internal`
  - `apps/api/routes/leads.py:65 ingest_leads->_create_lead_internal`
  - `apps/api/services/intake.py:68 create_lead->get_db`
  - `apps/api/services/intake.py:155 query_leads->get_db`

### PR-007: long_path
- **Score:** 57.0 | **Priority:** medium | **Governance:** NEEDS_HUMAN
- **Confidence:** 0.75 (raw=0.95, penalty=-0.2) — base=0.95 from 4+2 traces; penalty=-0.2 (fan-out=6 suggests orchestrator; calls 4 distinct downstream modules)
- **Occurrences:** 1
- **Intermediate role:** shared_composer (conf=0.7) -- calls 4 external modules; invokes 8 distinct functions including composition
- **Description:** Chain apps.api.routes.leads -> apps.api.services.operational -> apps.api.db: operational is a shared composition hub; persistent structural pattern, not confirmed pass-through (orchestrator signals: fan-out=6 suggests orchestrator; calls 4 distinct downstream modules)
- **Modules:** apps.api.routes.leads, apps.api.services.operational, apps.api.db
- **Impact:** structural | **Effort:** medium | **Risk:** low
- **Action:** evaluate_direct_path
- **Evidence** (4 sites):
  - `apps/api/routes/leads.py:165 get_actionable_leads->_get_actionable_leads`
  - `apps/api/routes/leads.py:173 get_actionable_worklist->_get_actionable_leads`
  - `apps/api/services/operational.py:42 get_actionable_leads->get_db`
  - `apps/api/services/operational.py:80 get_lead_pack_by_id->get_db`

### PR-005: long_path
- **Score:** 53.0 | **Priority:** medium | **Governance:** NEEDS_HUMAN
- **Confidence:** 0.75 (raw=0.95, penalty=-0.2) — base=0.95 from 13+1 traces; penalty=-0.2 (fan-out=5 suggests orchestrator; calls 3 distinct downstream modules)
- **Occurrences:** 1
- **Intermediate role:** shared_composer (conf=0.7) -- calls 3 external modules; invokes 5 distinct functions including composition
- **Description:** Chain apps.api.routes.leads -> apps.api.services.intake -> apps.api.services.scoring: intake is a shared composition hub; persistent structural pattern, not confirmed pass-through (orchestrator signals: fan-out=5 suggests orchestrator; calls 3 distinct downstream modules)
- **Modules:** apps.api.routes.leads, apps.api.services.intake, apps.api.services.scoring
- **Impact:** structural | **Effort:** medium | **Risk:** medium
- **Action:** evaluate_direct_path
- **Evidence** (3 sites):
  - `apps/api/routes/leads.py:49 create_lead->_create_lead_internal`
  - `apps/api/routes/leads.py:65 ingest_leads->_create_lead_internal`
  - `apps/api/services/intake.py:81 create_lead->calculate_lead_score`


## Watchlist
None.

## Ignored / Low-Confidence
None.

## Prohibited Connections
None detected. Architecture is clean.

## Graph Health
- Fan-out (all): 9 (apps.api.routes.leads) | (runtime): 9 (apps.api.routes.leads)
- Fan-in max: 9 | Protected: 3


## Decision Log

- **2159fce0** | status=resolved | **inactive**
  reason: routes.leads no longer imports db. Write ops extracted to services/intake.py, reads to services/operational.py.
  was: Prohibited: apps.api.routes.leads -> apps.api.db (Routes should not access DB di
- **c85f9b90** | status=resolved | **inactive**
  reason: Chain eliminated. routes.internal no longer imports routes.leads.
  was: Chain apps.api.routes.internal -> apps.api.routes.leads -> apps.api.services.sco
- **db9d3be7** | status=resolved | **inactive**
  reason: Chain eliminated. DB access moved to services layer.
  was: Chain apps.api.routes.internal -> apps.api.routes.leads -> apps.api.db: leads is

## Top 3 Actions
1. **extract_shared_function** -- apps.api.services.operational._get_actionable_leads called from 3 distinct functions (score=68.5)
2. **extract_shared_function** -- apps.api.services.intake._create_lead_internal called from 5 distinct functions (score=64.8)
3. **evaluate_direct_path** -- Chain apps.api.routes.internal -> apps.api.services.operational -> apps.api.db: operational is a shared composition hub; persistent structural pattern, not confirmed pass-through (orchestrator signals: fan-out=6 suggests orchestrator; calls 4 distinct downstream modules) (score=57.0)

## Known Limits
- Direct imports and attribute calls only
- Schema constructors suppressed; bootstrap excluded from runtime fan-out
- Orchestrator intermediates → watchlist with severity scoring
