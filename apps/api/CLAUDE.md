# CLAUDE.md — apps/api

> Local rules for the API module. Global CLAUDE.md applies in full.

---

## Scope

Owns: lead ingestion, persistence, scoring, action classification, operational outputs, reporting.

Must not absorb without approval: CRM behavior, delivery channel logic, automation execution, n8n integration.

---

## Before changing behavior

Read first: `docs/leads_runbook.md`, `docs/leads_decision_log.md`, `docs/operational_contracts.md`.

When docs and code disagree, code is the current contract. Do not "fix" code to match old docs without approval.

---

## Invariants

- Unique constraint: `(email, source)`. Do not change schema without approval.
- All ingestion converges to one internal creation path. Do not fork it. If the path does not fit, surface the gap instead of forking it.
- Do not reimplement logic that already exists elsewhere. Call it.

---

## What counts as a contract change

Any of these require approval:
- Changing response fields, types, semantics, or status codes
- Changing what a filter matches or excludes
- Changing result ordering
- Any behavioral change disguised as a refactor

A refactor that changes observable behavior is not a refactor.

---

## High-impact (triad required)

Scoring, action classification, persistence schema, public endpoint contracts.

---

## Validation

python -m pytest tests/api/test_api.py -v

For changes touching contracts, ingestion, persistence, scoring, classification, or reporting behavior, verify the affected behavior explicitly, not only by assumption.
