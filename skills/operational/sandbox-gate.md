# Title
sandbox-gate

## Mission
Require isolated validation before considering a block technically acceptable.

## When to use
Use this skill whenever a block:
- changes functional behavior,
- adds or modifies endpoints,
- affects workflows or automation,
- touches shared logic,
- or is intended to run with limited supervision.

## Required validation standard
A block is not considered truly acceptable unless it has validation evidence appropriate to its scope, such as:
- automated tests,
- sandbox execution,
- Docker-based reproducible validation,
- or another clearly stated isolated verification path.

## Required checks
1. Identify what can be validated automatically.
2. Run relevant tests.
3. Run sandbox and/or Docker validation when applicable.
4. Confirm whether validation covers:
   - expected behavior,
   - basic regressions,
   - and integration assumptions.
5. If validation is partial, explicitly state:
   - what was validated,
   - what was not validated,
   - and why.

## Rules
- Do not treat "looks correct" as validated.
- Do not report success when validation was skipped or incomplete.
- Do not hide test failures behind implementation summaries.
- Prefer reproducible validation steps over one-off manual impressions.
- If the environment fails, report it honestly and isolate likely causes.

## Output expectations
Every validated block should end with:
- tests run,
- sandbox/Docker evidence when applicable,
- pass/fail status,
- known validation gaps,
- and any follow-up needed to close those gaps.

## Non-goals
This skill does not decide business correctness on its own. Passing sandbox/tests is necessary evidence, not total proof of business validity.
