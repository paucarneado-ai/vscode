# Repair Packet Templates

Ready-to-use repair prompts for real failure classes. Copy the prompt skeleton, fill in specifics, run as a HARDEN block.

**Rules:**
- Max 8 templates. Consolidate rather than expand.
- Remove templates unused for 6 months.
- Each template must fit one screen (~30 lines).
- Do not duplicate runbooks or contracts — point to them.
- Every template has a `false_alarm_exit` — if checks pass, terminate immediately.

---

### 1. External intake contract break

**Trigger:** `POST /leads/external` returns unexpected status, wrong response shape, rejects valid payloads, or dedup stops working.
**Severity:** high
**Likely surfaces:** `POST /leads/external`, `POST /leads`
**Likely files:** `apps/api/routes/leads.py`, `apps/api/schemas.py`, `tests/api/test_api.py`

**First 3 commands:**
1. `pytest -k "external" -v`
2. `curl -X POST .../leads/external -d '{"name":"Test","email":"test@x.com","source":"trial:test"}' -H "Content-Type: application/json"`
3. Compare response shape against `operational_contracts.md` § POST /leads/external

**False alarm exit:** All targeted tests pass AND manual curl returns expected shape → no failure. Terminate.

**Docs to verify:** `docs/operational_contracts.md` § POST /leads/external

**Repair strategy:** GREEN — fix validation or response, update contract if shape changed.

**Prompt skeleton:**
```
MODE: HARDEN
GOAL: Fix POST /leads/external — [describe symptom]
SCOPE: apps/api/routes/leads.py, schemas.py, tests
DO NOT TOUCH: scoring logic, dedup logic unless directly broken
DONE WHEN: pytest -k "external" passes, response matches operational_contracts.md § POST /leads/external
```

---

### 2. Source intelligence mismatch

**Trigger:** `GET /internal/source-intelligence` totals disagree with `by_source` sum, recommendation is wrong, or outcomes don't match `/internal/source-outcome-actions`.
**Severity:** medium
**Likely surfaces:** `GET /internal/source-intelligence`, `GET /internal/source-outcome-actions`
**Likely files:** `apps/api/routes/internal.py` (source-intelligence endpoint), `tests/api/test_api.py`

**First 3 commands:**
1. `pytest -k "source_intelligence" -v`
2. Call endpoint, verify `totals.leads == sum(by_source[].leads)`
3. Verify all 6 outcome fields sum correctly

**False alarm exit:** All 6 targeted tests pass AND totals == sum(by_source) on live call → no failure. Terminate.

**Docs to verify:** `docs/operational_contracts.md` § GET /internal/source-intelligence

**Repair strategy:** GREEN — fix aggregation or recommendation logic. Check if `_source_outcome_recommendation()` changed.

**Prompt skeleton:**
```
MODE: HARDEN
GOAL: Fix source-intelligence — [describe mismatch]
SCOPE: apps/api/routes/internal.py (source-intelligence endpoint only), tests
DO NOT TOUCH: _source_outcome_recommendation() unless it is the root cause
DONE WHEN: pytest -k "source_intelligence" passes, totals == sum(by_source) for all fields
```

---

### 3. Followup CSV export break

**Trigger:** `GET /internal/followup-automation/export.csv` returns wrong columns, missing rows, broken quoting, unsanitized values, or doesn't match JSON endpoint selection.
**Severity:** high
**Likely surfaces:** `GET /internal/followup-automation/export.csv`, `GET /internal/followup-automation`
**Likely files:** `apps/api/routes/internal.py` (export endpoint), `tests/api/test_api.py`

**First 3 commands:**
1. `pytest -k "followup_export" -v`
2. Download CSV, verify header row matches `lead_id,to,subject,body,channel,priority,source,score,rating`
3. Compare row count with JSON endpoint total

**False alarm exit:** All 10 targeted tests pass AND CSV headers match contract AND row count matches JSON → no failure. Terminate.

**Docs to verify:** `docs/operational_contracts.md` § followup-automation/export.csv, `docs/followup_csv_runbook.md`

**Repair strategy:** GREEN — fix CSV writer, columns, or sanitization. Check `_FOLLOWUP_CSV_COLUMNS` and `_sanitize_csv_value()`.

**Prompt skeleton:**
```
MODE: HARDEN
GOAL: Fix followup CSV export — [describe symptom]
SCOPE: apps/api/routes/internal.py (CSV export endpoint only), tests
DO NOT TOUCH: followup selection logic unless selection is the root cause
DONE WHEN: pytest -k "followup_export" passes, CSV columns match docs/followup_csv_runbook.md
```

---

### 4. Daily actions / ops snapshot inconsistency

**Trigger:** `GET /internal/daily-actions` summary counts disagree with section items, or `GET /internal/ops/snapshot` arithmetic fails (`pending_dispatch != actionable - claimed`).
**Severity:** medium
**Likely surfaces:** `GET /internal/daily-actions`, `GET /internal/ops/snapshot`, `GET /internal/review`, `GET /internal/client-ready`
**Likely files:** `apps/api/routes/internal.py`, `apps/api/routes/leads.py` (`_get_actionable_leads`), `tests/api/test_api.py`

**First 3 commands:**
1. `pytest -k "daily_actions or snapshot" -v`
2. Call snapshot, verify `pending_dispatch == actionable - claimed`
3. Call daily-actions, verify summary counts match section lengths

**False alarm exit:** All targeted tests pass AND snapshot arithmetic holds AND daily-actions summary matches sections → no failure. Terminate.

**Docs to verify:** `docs/operational_contracts.md` § daily-actions, § ops/snapshot

**Repair strategy:** GREEN — identify which surface diverged. Usually `_get_actionable_leads()`, `_get_claimed_lead_ids()`, or `_REVIEWABLE_ACTIONS`.

**Prompt skeleton:**
```
MODE: HARDEN
GOAL: Fix daily-actions/snapshot inconsistency — [describe mismatch]
SCOPE: apps/api/routes/internal.py (affected endpoint), tests
DO NOT TOUCH: claim logic or actionable-leads logic unless directly broken
DONE WHEN: pytest -k "daily_actions or snapshot" passes, arithmetic holds on live call
```

---

### 5. Cross-surface invariant failure

**Trigger:** Any of the 3 invariant tests fails: `snapshot.pending_review != review.total`, `snapshot.pending_review != daily.pending_review + daily.client_ready`, or `client_ready.total != daily.client_ready`.
**Severity:** high
**Likely surfaces:** `GET /internal/ops/snapshot`, `GET /internal/review`, `GET /internal/daily-actions`, `GET /internal/client-ready`
**Likely files:** `apps/api/routes/internal.py`, `apps/api/routes/leads.py`, `tests/api/test_api.py`

**First 3 commands:**
1. `pytest -k "snapshot_pending_review_equals or client_ready_total_equals" -v`
2. If failure: identify which invariant broke and which surface value is wrong
3. Grep for recent changes to `_REVIEWABLE_ACTIONS`, `_get_actionable_leads()`, or `_get_claimed_lead_ids()`

**False alarm exit:** All 3 invariant tests pass → no failure. Terminate.

**Docs to verify:** `docs/operational_contracts.md` § ops/snapshot naming note, § daily-actions naming note

**Repair strategy:** YELLOW — fix the surface that diverged, not the test. The invariants are the contract.

**Prompt skeleton:**
```
MODE: HARDEN
GOAL: Fix cross-surface invariant — [which invariant, which test failed]
SCOPE: apps/api/routes/internal.py (divergent surface only)
DO NOT TOUCH: invariant tests — they define the contract
DONE WHEN: pytest -k "snapshot_pending_review_equals or client_ready_total_equals" passes
```

---

### 6. Documentation drift on changed surface

**Trigger:** Drift checkpoint flags `updated` needed but wasn't done, or manual inspection reveals contract section contradicts endpoint behavior.
**Severity:** medium
**Likely surfaces:** Any endpoint whose contract, response shape, or query params changed
**Likely files:** `docs/operational_contracts.md`, `docs/component_index.md`, `docs/system_map.md`

**First 3 commands:**
1. Call the endpoint, compare output against its `operational_contracts.md` section
2. Check status table row exists for the endpoint
3. `pytest -v` (full regression to confirm code is correct — docs are wrong, not code)

**False alarm exit:** Endpoint output matches contract section exactly AND status table row exists → no drift. Terminate.

**Docs to verify:** `docs/operational_contracts.md` status table + relevant § section

**Repair strategy:** GREEN — update docs to match code. Never change code to match stale docs.

**Prompt skeleton:**
```
MODE: HARDEN
GOAL: Fix doc drift — [which endpoint/surface, what disagrees]
SCOPE: docs/operational_contracts.md, docs/component_index.md, docs/system_map.md (only affected sections)
DO NOT TOUCH: code, tests, schemas
DONE WHEN: contract section matches actual endpoint response shape, status table is complete
```
