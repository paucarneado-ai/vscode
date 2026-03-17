# apps/api/CLAUDE.md

Purpose: keep MVP API work narrow, useful, verified.

If a rule here does not change decisions, reduce errors, or stop drift, shorten or remove it.
No pretty prose. Only operational value.

## DEFAULTS
Prefer:
- reuse
- smaller scope
- fewer files
- fewer branches
- fewer fields
- explicit verification
- stopping early

Avoid:
- generalization
- future-proofing
- hidden phase 2 work
- polishing closed blocks
- platform drift

## CLASSIFY FIRST
Before any non-trivial edit, classify as exactly one:
- BUILD
- HARDEN
- BUGFIX
- CONTRACT CLARIFICATION
- DOC/TRUTHFULNESS
- ALREADY DONE
- NOT WORTH DOING NOW

If `ALREADY DONE` or `NOT WORTH DOING NOW`, stop.

## REVIEW FLOW

Advisory only — no enforcement hooks or CI gates exist. Claude Code follows these rules by reading this file.

Risk classes:
- GREEN: 1–3 files, no persistence/dependency/protected-area/contract changes, cheap rollback
- YELLOW: 3–6 files, internal endpoint/schema/bot changes, visible operational behavior, docs+tests+route style blocks
- RED: persistence/schema, dependencies, protected areas (.claude/*, skills/*, deploy/*, Dockerfile, docker-compose*, README.md, .gitignore), destructive cleanup, global governance, architecture/foundation, high semantic risk

Activation:
- YELLOW/RED BUILD/HARDEN: run Scope Critic (`POST /internal/scope-critic`) before building
- YELLOW/RED block closure: run Proof Verifier (`POST /internal/proof-verifier`) before closing
- GREEN: skip unless operator asks

Stop:
- Scope Critic returns `block` → do not build
- Proof Verifier returns `not_close` → do not close
- `watch` from either tool = proceed, but record noted concerns in the block report
- RED blocks require operator approval before build, even if Scope Critic returns `ok` or `watch`

Autonomy:
- GREEN: may build autonomously
- YELLOW: may build if Scope Critic does not block
- RED: must not build without operator approval
- Never autonomously delete, archive, or make irreversible governance changes

## CLOSED BLOCK RULE
Do not reopen a closed block unless there is:
- real bug
- real contract mismatch
- real business gain
- real risk reduction

"Could be nicer" is not enough.

## STOP IF
- new dependency
- persistence change
- scoring change
- material public contract change
- drift toward platform / CRM / frontend productization

If any appear: stop and ask.

## REQUIRED PRE-EDIT OUTPUT
1. Classification
2. Business goal
3. Why now
4. Smallest acceptable implementation
5. Files to change
6. What stays untouched
7. Main risk
8. Verification target
9. Approval triggers

No edits before this.

## REQUIRED FINAL OUTPUT
- Decision
- Why this block exists
- Changed
- Verified
- Not verified
- Left untouched
- Watch signals (if any)
- Follow-up / debt
- Approval needed [yes/no]

## ANTI-COMPLACENCY
Do not write casually:
- done
- complete
- no debt
- production-ready
- fully supported

Prefer:
- accepted for MVP
- intentionally deferred
- verified at contract level
- residual debt remains

## PROJECT TRUTH
- External intake already exists.
- Demo intake already exists.
- Several internal areas are already "good enough" for MVP.
- Prefer blocks closer to business signal.
- Do not touch `tasks/todo.md` unless explicitly asked.
