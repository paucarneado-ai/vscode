# CLAUDE.md

> Global operating rules for Claude Code in this repository.
> Local module `CLAUDE.md` files may add stricter rules for their scope.
> Priority:
> 1. human instruction
> 2. explicit module-local rule
> 3. this global file

---

## 1. Project posture

OpenClaw is an early-stage modular system. MVP first. Build the smallest clean core and the next useful module without contaminating the base.

---

## 2. Non-negotiable rules

- Inspect before claiming. Do not assume repository state, module status, or architecture state.
- Do not invent completeness, contracts, readiness, or test results.
- Do not expand scope silently.
- Do not refactor outside scope without approval.
- Do not add weight where a thinner solution works.
- Do not simulate clarity when intent, contract, or acceptance criteria are materially ambiguous.
- If speed, cleanliness, and scope control conflict, surface the tradeoff. Do not improvise it silently.
- Prefer additive, bounded change over disruptive rewrite unless rewrite is clearly lower-risk.
- If the task is local, keep it local.

If the current approach is failing:
- stop
- reduce scope
- re-plan
- change approach

---

## 3. Operator and mode

For any non-trivial task, the human should declare:
- OPERATOR
- MODE: BUILD or HARDEN
- GOAL
- SCOPE
- CONSTRAINTS
- DONE WHEN

Do not guess operator or mode from tone or habit.

Mode meaning:
- BUILD = larger coherent implementation block
- HARDEN = precision fix, contract tightening, edge cases, tests, reliability work

If MODE is missing for a non-trivial task:
- infer cautiously from task nature
- state the chosen mode before proceeding
- default conservative when risk is non-trivial

BUILD-specific rules:
- define contract first for new endpoints, integrations, or interfaces
- do not create broad abstractions before one real use proves the shape

HARDEN-specific rules:
- do not turn a fix into a rewrite
- do not reopen settled architecture without cause

---

## 4. Planning and execution

For any non-trivial task, think first.

Minimum plan:
- objective
- constraints
- risks
- affected files or areas
- minimum acceptable implementation
- verification method

Execution:
- one coherent chunk at a time
- keep feature work, debugging, and refactor work separated when possible
- document meaningful deviations
- do not silently enlarge the problem

---

## 5. Context discipline

Do not rely on chat history alone.

Required files:
- `CLAUDE.md`
- `tasks/todo.md`
- `tasks/lessons.md`
- `SCRATCHPAD.md`

Rules:
- keep one conversation per feature or task block when possible
- do not drag noisy context forward
- when context degrades, write down critical facts and reset
- do not duplicate stable rules without reason

Do not store in this global file unless truly global. Endpoint contracts, module debt, runbooks, local architecture details belong in module-local docs.

When work depends on current contracts, operational behavior, debt, or frozen decisions of a module, inspect that module's local docs (`docs/`, local `CLAUDE.md`, decision logs, runbooks) before proceeding.

---

## 6. Reopen, foundation, and reuse

Do not reopen a closed module unless:
- a real bug blocks progress
- the change prevents likely rework
- the change materially improves reuse or safety
- the human explicitly prioritizes reopening it

Foundational work is allowed when it creates reusable infrastructure, prevents likely rework, reduces material risk, or enables a future strategic vertical without contaminating the current MVP.

For external integrations, prefer the thinnest usable contract first.

---

## Non-monetizing block survival rule

Do not keep or build a block only because it sounds foundational.

A block that does not monetize directly or clearly within 30–60 days is rejected by default.

It may still be accepted only if it clearly satisfies at least one of these:
- creates reusable infrastructure
- prevents likely rework
- reduces meaningful risk
- enables a clearly plausible future capability or vertical
- materially improves system cohesion, reliability, or maintainability

And only if all of these are also true:
- scope is small and controlled
- it does not displace better commercial, validation, or automation work without strong reason
- it does not add disproportionate complexity
- its value can be explained concretely, not abstractly
- there is a plausible way to verify later that it actually paid off

Required before approval:
- state exactly which exception condition it satisfies
- state what concrete future value it enables or what concrete risk/rework it avoids
- state why doing it now is better than doing it later
- state what later signal would show that keeping it was correct

If a non-monetizing block does not meet that standard:
- reject it, or
- archive it as an idea,
but do not build it now.

"Foundational" alone is not a justification.

---

## 7. Lessons and documentation

`tasks/lessons.md` stores repeated mistakes and corrective patterns.

Update it when the human corrects an important mistake, the same mistake repeats, or a new rule would clearly prevent future rework. Do not fill it with noise.

Write documentation only for important decisions, future-relevant contracts, behavior likely to be forgotten, or handoff-critical context. Do not restate obvious framework basics.

---

## 8. Engineering rules

- Prefer explicit typing and validation at boundaries.
- Tests are required for meaningful behavior changes.
- Minimum before merge: happy path + obvious failure path + relevant edge case.
- Do not add new dependencies without clear justification. Every dependency is maintenance debt.
- SQL must use bind parameters. Never interpolate SQL directly.
- Never hardcode secrets. Use environment variables or approved config paths.
- Validate inputs at API and system boundaries.

---

## 9. Subagents

Use subagents only when they materially improve focus, reduce context pollution, or allow useful parallel work. One subagent = one responsibility. Do not fragment work without reason.

---

## 10. Approval boundaries

You may generally: plan, propose, implement bounded changes, create or edit normal project files, write tests, harden within scope.

You must stop and seek explicit approval before:
- adding new dependencies
- significant database schema or persistence changes
- changing scoring or other core decision logic
- changing authentication, authorization, or API-key behavior
- altering deployment, Docker, CI/CD, or infra assumptions
- destructive operations or deleting important files
- editing `.claude/*`, `skills/*`, or other governance-critical files without explicit instruction
- refactors affecting multiple modules
- incompatible public API contract changes
- replacing a simple clean path with a substantially heavier one
- expanding scope far beyond the task

Protected files — do not touch without explicit human instruction:
`README.md`, `Dockerfile`, `docker-compose*`, `.gitignore`, `.claude/*`, `skills/*`

When in doubt, surface the decision instead of guessing.

---

## 11. High-impact rule

For high-impact work, use triad: implementation + review/testing + human approval.

Apply triad to: scoring or core decision engines, lead pack generation, authentication/authorization/security-critical behavior, any change explicitly marked high-impact.

Do not apply triad mechanically to deterministic low-risk work.

---

## 12. Verification and reporting

Before declaring completion, verify appropriately. Never claim checks that were not run. State the exact command or method used. State what was not executed.

Standard commands:
python -m pytest tests/api/test_api.py -v
python -m pytest tests/ -v
ruff check .
ruff format .

For any non-trivial task, end with exactly:
- Changed
- Verified
- Not verified
- Left untouched
- Follow-up / debt

---

## 13. Definition of done

A task is done only when:
1. the requested objective is implemented or resolved
2. the result is verified appropriately
3. `tasks/todo.md` is updated when the task was non-trivial
4. remaining debt or follow-up is explicit
5. no obvious unresolved contradiction remains

---

## 14. Working style

Be direct. Be precise. Do not overtalk. Do not overbuild.
