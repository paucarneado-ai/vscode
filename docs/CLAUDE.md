# docs/CLAUDE.md

Purpose: preserve verified truth.

Docs are not marketing.
Docs are not cleanup theater.
Docs must reflect reality.

If a rule here does not make docs more truthful, reduce ambiguity, or prevent rework, shorten or remove it.
No pretty prose. Only truth-preserving value.

## FIRST RULE
Do not document desired reality.
Document verified reality.

If code, tests, and docs disagree, docs lose.

## AUTHORITY ORDER
1. `docs/operational_contracts.md`
2. `docs/leads_runbook.md`
3. session notes / todo files / reports

Temporary notes must not redefine contracts.

## BEFORE EDITING DOCS
Check:
- code
- schema if relevant
- tests for exact behavior

Then classify the doc change as:
- truthful reflection
- wording clarification
- mismatch exposure
- attempt to document unbuilt behavior

If it is unbuilt behavior, do not write it as present reality.

## FORBIDDEN
Do not:
- overclaim
- deodorize debt
- blur demo with product
- blur internal contract with public contract
- call something supported because it happens to work
- write no debt casually

## REQUIRED SEPARATION
Always distinguish:
- public contract
- internal operational contract
- demo-only surface
- deferred work
- known debt
- not verified

## DEBT RULE
If debt exists, name it.
If something is deferred, say why.
If something is not verified, say so.

## EXAMPLE RULE
Examples must be:
- minimal
- current
- copy-paste useful
- honest about omissions

If an example shows only a subset, say so.

## SESSION REPORT RULE
Reports must say:
- what changed
- what was verified
- what was not verified
- what remained untouched
- residual debt
- approval needed

No victory language.
No fake completeness.

## PROJECT TRUTH
- `POST /leads/external` is canonical MVP external intake.
- `GET /demo/intake` is demo-only.
- This project already lost concrete operational detail once under cleaner rewrites.
- Do not repeat that.
