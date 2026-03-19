# Plan: Real External Followup Execution MVP

## Context

The followup stack is fully built internally:
- `/internal/followup-queue` — human review surface
- `/internal/followup-handoffs` — operator instruction surface
- `/internal/followup-automation` — machine-consumable payloads
- `followup_bridge.py` — consumer bridge that maps automation items to execution-ready `BridgeItem`s (to, subject, body, channel, priority)

**What's missing:** There is no way for an operator or external tool to actually *consume* the followup items as a real artifact. The automation endpoint returns JSON, which is useful for n8n polling, but there is no downloadable/exportable surface — no CSV, no flat file, nothing an operator can open in a spreadsheet, paste into an email tool, or feed to a simple script.

**Existing pattern:** `/internal/handoffs/export.csv` already exports handoff items as CSV with sanitization, `StringIO`, `csv.writer`, `PlainTextResponse`, and Content-Disposition attachment header. This exact pattern can be reused.

## What exact pain this solves

An operator who runs the followup workflow today must:
1. Call `/internal/followup-automation` (JSON)
2. Parse the nested payload structure manually
3. Extract to/subject/body/priority fields
4. Manually compose emails or paste into a tool

With a CSV export, the operator can:
1. Download one file
2. Open in any spreadsheet/email tool
3. Execute the followup batch directly

This is the difference between "the system knows what to do" and "the operator can actually do it."

## Chosen option: `GET /internal/followup-automation/export.csv`

A single CSV export endpoint that reuses the bridge's mapping logic to produce a flat, operator-ready file.

**Columns:** `lead_id, to, subject, body, channel, priority, source, score, rating`

These are exactly the `BridgeItem` fields — the bridge already does the work of flattening the automation payload into execution-ready rows. The endpoint imports and calls `run_followup_bridge()` with the same `TestClient` pattern (or direct DB call), then writes rows to CSV.

**Actually simpler:** The endpoint can directly reuse the same SQL query from `/internal/followup-automation` and apply the same deterministic subject/message templates inline, without importing the bridge. This avoids a circular dependency (route importing bridge that calls back into the route). The bridge's mapping is trivial — 3 lines of template lookup + field extraction.

**Final design:** Inline the template logic directly (same `_SUBJECT_BY_RATING` dict, same SQL query pattern as the existing followup-automation endpoint). No bridge import needed.

**Query params (matching handoffs/export.csv pattern):**
- `source: str | None` — filter by lead source
- `limit: int | None` — cap output rows

## Rejected simpler option: "Just tell operators to use the JSON endpoint"

Why rejected: Operators should not have to parse nested JSON to execute a followup batch. The handoffs surface already has CSV export — followup automation should too, for consistency and real usability.

## Rejected more ambitious option: "Build a full execution orchestrator with status tracking"

Why rejected: Violates every constraint. No persistence changes, no scheduler, no new dependencies. A CSV export is the thinnest useful artifact that creates real operational value immediately.

## Exact files to change

| File | Change | Size |
|------|--------|------|
| `apps/api/routes/internal.py` | Add `GET /internal/followup-automation/export.csv` endpoint, add `_FOLLOWUP_CSV_COLUMNS` constant, add `_FOLLOWUP_SUBJECT_BY_RATING` dict | ~45 lines |
| `apps/api/schemas.py` | No change needed — CSV uses PlainTextResponse, not a Pydantic model |
| `tests/api/test_api.py` | Add tests: shape, columns, content, source filter, limit, empty, sanitization, consistency with JSON endpoint | ~80 lines |
| `docs/operational_contracts.md` | Add contract section for the new export endpoint | ~25 lines |

## Files NOT touched

- `apps/api/automations/followup_bridge.py` — not modified, bridge stays as-is
- `apps/api/schemas.py` — no new schema needed
- `apps/api/routes/leads.py` — unrelated
- All protected files
- No persistence changes
- No new dependencies

## Exact tests to add

1. `test_followup_export_csv_shape` — 200, text/csv, Content-Disposition header
2. `test_followup_export_csv_columns` — first row matches expected columns
3. `test_followup_export_csv_content` — rows contain correct lead data for no_answer leads
4. `test_followup_export_csv_excludes_non_no_answer` — leads with other outcomes absent
5. `test_followup_export_csv_excludes_claimed` — claimed leads absent
6. `test_followup_export_csv_source_filter` — source param filters correctly
7. `test_followup_export_csv_limit` — limit param caps rows
8. `test_followup_export_csv_empty` — no leads returns header-only CSV
9. `test_followup_export_csv_consistent_with_json` — same lead_ids in same order as `/internal/followup-automation`

## Reuse

- `_get_claimed_lead_ids()` — existing helper
- `_sanitize_csv_value()` — existing CSV sanitization
- `PlainTextResponse` — existing import
- `io.StringIO` + `csv.writer` — existing pattern from handoffs export
- SQL query pattern — same JOIN as `/internal/followup-automation` endpoint
- Subject templates — same deterministic mapping as bridge (`high` → "Following up — let's connect this week", etc.)

## Risk assessment

- **Contract risk:** LOW — new endpoint, no existing contract modified
- **Logic risk:** LOW — reuses existing query pattern and deterministic templates
- **Regression risk:** LOW — additive only, no changes to existing endpoints
- **Scope creep risk:** LOW — one endpoint, focused tests, one doc section

## Explicitly out of scope

- Email sending
- WhatsApp / SMS
- Scheduling / retries
- Persistence changes
- Bridge modification
- n8n integration code
- Governance bot changes
- Any new dependencies

## Verification

```bash
python -m pytest tests/api/test_api.py -k "followup_export" -v
python -m pytest tests/ -v
```
