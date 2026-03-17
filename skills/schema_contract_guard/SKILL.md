# Schema Contract Guard

## Mission
Catch contract-breaking changes before they ship.

## When to use
Before any edit that touches:
- Pydantic schemas (request or response models)
- response field names, types, or semantics
- status codes or error shapes
- query parameter names, types, or defaults
- validation rules or dedup behavior

## Procedure
1. Read the current schema or response model.
2. Read the current test assertions for that endpoint.
3. Read the `operational_contracts.md` entry if one exists.
4. Identify what is changing: field added, field removed, field renamed, type changed, status code changed, validation tightened/loosened.
5. Classify: additive (low risk, verify tests), widening (review required), breaking (needs approval).
6. If breaking: stop and state what breaks and for whom.
7. If widening: state what new inputs or outputs consumers must now handle.
8. If additive: verify existing tests still pass with the new shape.
9. Update `operational_contracts.md` to match the new truth.

## Classification guide
- Adding an optional field to a response: **additive**.
- Adding a required field to a request: **breaking**.
- Removing or renaming any response field: **breaking**.
- Changing a field type: **breaking**.
- Tightening validation (rejecting previously accepted input): **breaking**.
- Loosening validation (accepting previously rejected input): **widening** — contract surface grows; consumers may depend on strict guarantees.
- Adding an optional field to a request: **additive**.
- Changing a status code: **breaking**.

## Required output
- **Change**: what moved (field/type/status/validation)
- **Classification**: additive / widening / breaking
- **Impact**: who or what is affected
- **Tests checked**: which assertions confirm contract safety
- **Docs updated**: yes/no
- **Approval needed**: yes/no

## Rules
- Do not change a response shape "for cleanliness" without checking consumers.
- Do not add required request fields without justification.
- Do not assume no consumers exist.
- Test count is not proof of contract safety. Check the actual assertions.

## Non-goals
Not for designing new schemas. Not for internal-only helper types.
