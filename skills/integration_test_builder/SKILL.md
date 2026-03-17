# Integration Test Builder

## Mission
Design tests that verify an entity flows correctly across multiple API surfaces.

## When to use
When a block adds or changes behavior that spans more than one endpoint.
When verifying that data entering via endpoint A appears correctly in endpoints B and C.

## Procedure
1. Identify the entry point (the endpoint that creates or modifies the entity).
2. Identify downstream surfaces where the entity should appear after creation.
3. Identify surfaces where the entity should NOT appear (excluded by eligibility, status, or ownership).
4. Write one test per meaningful flow path:
   - create entity via entry point
   - assert presence/absence in each downstream surface
   - assert field values are consistent across surfaces
5. If state changes affect visibility (e.g., claims, status transitions), test the full cycle:
   - create, verify visible
   - change state, verify excluded
   - reverse state, verify visible again

## Required output
Before writing tests, state:
- **Entry point**: endpoint under test
- **Downstream surfaces**: where the entity should appear
- **Exclusion surfaces**: where it should not appear and why
- **Flow paths**: list of distinct paths to test
- **Isolation strategy**: how each test avoids collisions with other tests
- **Key assertions**: what specific values or conditions each flow path must verify

## Rules
- Each flow test must use unique identifiers to avoid collisions with other tests.
- Do not test internal logic (scoring, classification) inside flow tests. Those have their own tests.
- Do not create fixture systems or shared state. Inline setup per test.
- If a flow test reveals an inconsistency between surfaces, that is a real finding. Report it.

## Non-goals
Not for unit tests. Not for testing a single endpoint in isolation.
