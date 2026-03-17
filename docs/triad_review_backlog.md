# Triad Review Backlog

> Generated: 2026-03-16 — controlled sweep of all built modules.
> Findings are ordered by module, then severity.

---

## TRB-001: Undocumented created_from / created_to filter parameters

- **Module:** Leads Core
- **Title:** created_from and created_to query params exist in code but are absent from operational_contracts.md
- **Category:** doc/code mismatch
- **Severity:** medium
- **Evidence:**
  - Code: `apps/api/routes/leads.py:324-325` — `created_from: str | None = None, created_to: str | None = None`
  - Same params on GET /leads/summary (line 341) and GET /leads/export.csv (line 470)
  - Docs: `docs/operational_contracts.md` lines 26-27 — lists `source, min_score, limit, offset, q` only. No mention of date filters.
  - Confirmed: `grep` for `created_from` in operational_contracts.md returns zero matches.
- **Why it matters:** Public API surface not documented. Clients may discover and rely on undocumented behavior. Violates docs/CLAUDE.md: "Document verified reality."
- **Recommended action:** Add created_from/created_to to the GET /leads, GET /leads/summary, and GET /leads/export.csv contract descriptions in operational_contracts.md.
- **Auto-fix allowed:** no — changes documented public API contract surface, needs human review of wording
- **Human review required:** yes
- **Files affected:** `docs/operational_contracts.md`
- **Status:** resolved — doc updated in operational_contracts.md (summary table + detailed contract section)

---

## TRB-002: SQLite-specific date concatenation in created_to filter

- **Module:** Leads Core
- **Title:** Date filter uses SQLite `||` string concatenation with bind parameter
- **Category:** low-risk hardening
- **Severity:** low
- **Evidence:**
  - Code: `apps/api/routes/leads.py:286` — `conditions.append("created_at <= ? || ' 23:59:59'")`
  - This produces valid SQL: `created_at <= '2025-06-30' || ' 23:59:59'` → `created_at <= '2025-06-30 23:59:59'`
  - Works correctly in SQLite (string concatenation with bind param). Tests pass.
- **Why it matters:** Non-obvious pattern. Not portable to other databases. A developer unfamiliar with SQLite's `||` operator could misread this as a logical OR.
- **Recommended action:** Consider rewriting to concatenate in Python before binding: `params.append(created_to + " 23:59:59")`. Low priority — works correctly today.
- **Auto-fix allowed:** no — code change in leads core (frozen D7)
- **Human review required:** yes
- **Files affected:** `apps/api/routes/leads.py`
- **Status:** deferred — accepted low-priority debt, no code change

---

## TRB-003: Redundancy checks table uses "Check" column label but findings use "type" field

- **Module:** Governance bots (redundancy)
- **Title:** Redundancy contract table column name doesn't match response schema field
- **Category:** naming/discoverability issue
- **Severity:** low
- **Evidence:**
  - Docs: `docs/operational_contracts.md:310-315` — table header is "Check" with values `skills_redundant_candidates`, `dormant_stubs`, `claude_md_literal_duplication`
  - Schema: `apps/api/schemas.py` — `RedundancyFinding` has field `type: str`, not `check: str`
  - Code: internal.py — creates findings with `type="overlap"` or `type="dormant"`, not the check names shown in docs
- **Why it matters:** Reader of docs expects a "check" field in the response. The actual response has a "type" field with different values. Confusing but not functionally broken.
- **Recommended action:** Semantic decision needed: either (a) rename doc table column from "Check" to "Type" and update values to match code, or (b) add a `check` field to the schema. Option (a) is simpler.
- **Auto-fix allowed:** no — requires semantic decision on whether to change docs or schema
- **Human review required:** yes
- **Files affected:** `docs/operational_contracts.md` (or `apps/api/schemas.py` + `apps/api/routes/internal.py` if schema change)
- **Status:** resolved — doc table updated to show `type` field values and clarify `RedundancyFinding` schema alignment

---

## Auto-fixes applied during this sweep

See the "Safe fixes applied" section at the end of this file for the list of changes made directly.

### AF-001: Test count updated 461→471 in system_map.md (2 locations)
### AF-002: Drift Detector added to system_map.md named constructs table
### AF-003: Drift Detector added to system_map.md quality bots table
### AF-004: Drift Detector added to system_map.md active list
### AF-005: Drift Detector added to component_index.md as component entry
### AF-006: scope-guard architecture skill row corrected in component_index.md
