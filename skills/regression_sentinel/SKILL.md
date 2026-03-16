# Regression Sentinel

## Mission
Given a code change, identify what might break and what to rerun.

## When to use
After any edit to route, schema, service, or shared logic.
Before declaring a block verified.

## Procedure
1. List the files changed in this block.
2. For each changed file, identify:
   - which endpoints call this code (direct or indirect)
   - which tests exercise those endpoints
   - which schemas are used in those endpoints
3. Map the blast radius:
   - **direct**: tests that import or call the changed code
   - **indirect**: tests for endpoints that use shared logic touched by the change
4. Run direct tests first. If any fail, stop and investigate.
5. Run indirect tests. If any fail, determine whether the change caused it.
6. If a test fails, do not modify the test to make it pass. Investigate whether the change introduced a regression.

## Required output
- **Files changed**: list
- **Blast radius**: direct and indirect test targets, named specifically
- **Tests run**: which, pass/fail
- **Regressions found**: description or "none"
- **Action**: continue / investigate / stop and report to operator
- **Coverage gap**: yes/no

## Rules
- "All 283 tests pass" is not a blast radius analysis. Name the specific tests that matter.
- If no tests cover the changed behavior, say so explicitly.
- Do not skip indirect tests because direct tests passed.

## Non-goals
Not for designing new tests. Not for deciding what to build.
