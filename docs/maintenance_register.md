# Maintenance Register

Compact register of critical surfaces, failure signals, and repair hints.

**Rules:**
- Max 12 items. If this file grows beyond that, something is wrong.
- Only add a new item after a real failure, near-miss, or repeated maintenance burden.
- Remove items that have not produced a meaningful trigger in 6 months.
- Repair playbooks are hints, not runbooks. Keep them under 2 lines.
- Every row with severity high must map to a repair template in `docs/repair_packet_templates.md`.

---

| Item | Type | Owner | Review mode | Business impact | Due trigger | Check method | Failure signal | Severity | Repair playbook | Template |
|---|---|---|---|---|---|---|---|---|---|---|
| `POST /leads/external` | contract | operator | post-change | revenue | Endpoint, schema, source validation, or response shape change | `pytest -k "external" -v` + compare response vs contracts § POST /leads/external | 422 on valid payload, wrong response shape, dedup not firing | high | Run targeted tests. Update contract if shape changed | #1 |
| `GET /internal/source-intelligence` | surface | operator | post-change | ops | Endpoint, outcome logic, `_source_outcome_recommendation()`, or actionable-leads change | `pytest -k "source_intelligence" -v` + verify `totals == sum(by_source)` | Totals/by_source mismatch, wrong recommendation, crash on empty DB | medium | Run 6 targeted tests. Cross-check totals consistency | #2 |
| `GET /internal/followup-automation/export.csv` | surface | operator | post-change | revenue | Followup selection, CSV columns, subject templates, or sanitization change | `pytest -k "followup_export" -v` + download CSV, open in spreadsheet | Wrong columns, missing sanitization, broken quoting | high | Run targeted tests. Compare CSV headers vs contract | #3 |
| `GET /internal/daily-actions` | surface | operator | post-change | ops | Review/client-ready/followup logic, `_DAILY_CAP`, or source warning rules change | `pytest -k "daily_actions" -v` + call endpoint, verify summary counts | Summary counts disagree with section lengths, cap not applied | medium | Run targeted tests. Verify summary counts vs sections | #4 |
| `GET /internal/ops/snapshot` | surface | operator | post-change | ops | Actionable-leads logic, claim logic, or `_REVIEWABLE_ACTIONS` change | `pytest -k "snapshot" -v` + verify `pending_dispatch == actionable - claimed` | Arithmetic mismatch, stale counts | medium | Run targeted + invariant tests | #5 |
| Cross-surface invariants | ops | operator | post-change | ops | Any change to review, client-ready, daily-actions, or ops/snapshot logic | `pytest -k "snapshot_pending_review_equals or client_ready_total_equals" -v` | Any invariant test fails | high | Run 3 invariant tests. Fix divergent surface, not test | #5 |
| `docs/operational_contracts.md` | doc | operator | trigger_only | docs | Any block that adds/changes endpoint, schema, surface, response shape, or query param | Drift checkpoint in block closure — compare status table vs code | Endpoint in code but not in table, or section contradicts response | medium | Update status table row + contract section | #6 |
