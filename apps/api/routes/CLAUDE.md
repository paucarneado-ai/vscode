# apps/api/routes/CLAUDE.md

Purpose: govern HTTP contract work.

Routes are contract surfaces.
Make the smallest correct HTTP change and prove it.

If a rule here does not change route decisions, prevent contract drift, or reduce bad edits, shorten or remove it.
No pretty prose. Only execution value.

## BEFORE TOUCHING A ROUTE
Read:
- target route
- related schema
- relevant tests

Then decide which is true:
- behavior missing
- behavior exists but needs hardening
- behavior exists and only docs are weak
- behavior already exists and no work is needed

Say which one it is before editing.

## DEFAULTS
Prefer:
- harden existing route
- document existing route
- test existing route

Avoid:
- new endpoint
- duplicated logic
- hidden policy in route code
- widened contract "for future use"

## NEW ENDPOINT RULE
A new endpoint needs a real reason.
"Cleaner" is not a reason.
"Useful later" is not a reason.

## REUSE RULE
Do not duplicate:
- creation logic
- validation logic
- normalization logic
- dedup logic

If reuse is messy, say so.
Do not fork behavior quietly.

## THIN ROUTE RULE
A route may:
- parse input
- call logic
- map output
- return response

A route may not become:
- workflow engine
- policy engine
- integration platform
- dumping ground

## CONTRACT-RISK RULE
Treat these as high-risk:
- request shape
- response shape
- status codes
- validation behavior
- dedup/conflict behavior
- source/origin semantics

If any move, say it explicitly.

## INTERNAL OPS WARNING
If touching internal ops surfaces, assume semantic risk.

Do not casually change:
- dispatch membership
- claim/release meaning
- review visibility
- client-ready criteria
- worklist semantics
- snapshot counts
- business-relevant ordering

If the change affects who appears where, when, or why, it is a semantic change.

## TEST RULE
Do not say "covered" unless the exact change is tested.

Minimum useful verification usually includes:
- happy path
- invalid payload
- conflict/duplicate path if relevant
- special status path if relied upon
- semantic consistency if internal ops are involved

Test count is not proof.

## STOP IF
- second endpoint might be unnecessary
- route change implies persistence work
- route work becomes broader than the business outcome
- task drifts into frontend or integration platform work
- task starts touching side files outside scope without explicit reason

Stop. Shrink. Re-state.

## PROJECT TRUTH
- `POST /leads/external` already exists.
- `GET /demo/intake` is demo-only.
- Internal ops is already serious enough for MVP.
- Do not create plumbing for psychological progress.
