# Title
scope-guard

## Mission
Protect the current implementation block from scope creep, opportunistic refactors, silent reinterpretation of product decisions, and unnecessary architectural expansion.

## When to use
Use this skill in every meaningful implementation block, especially when:
- the task touches existing business logic,
- the block could easily expand into adjacent work,
- there are frozen product decisions already documented,
- or the change affects a live MVP path.

## Required checks
Before implementation:
1. Identify the explicit goal of the current block.
2. Identify explicit non-goals.
3. Read the master context and treat frozen decisions as binding.
4. Identify whether the requested change touches:
   - persisted schema,
   - business scoring,
   - critical automation behavior,
   - or public/internal contracts.

During implementation:
5. Stay inside the smallest scope that completes the block.
6. Reuse existing logic where possible instead of opening side paths.
7. Record any useful but non-essential improvement as follow-up instead of implementing it inline.

## Rules
- Do not reopen frozen business decisions unless there is:
  - a strong contradiction,
  - material risk,
  - or real technical impossibility.
- Do not change persisted schema without explicit justification.
- Do not change business scoring logic because a different version seems cleaner.
- Do not add abstractions, layers, or patterns for hypothetical future use.
- Do not refactor unrelated code during the block unless doing so:
  - directly unblocks the block,
  - prevents highly probable rework,
  - or reduces material risk.
- Treat the master context as the source of truth for scope, priorities, and constraints.

## Output expectations
At the end of the block, explicitly state:
- what was implemented,
- what was intentionally left out,
- what was deferred,
- and whether any scope pressure was detected and rejected.

## Non-goals
This skill is not for maximizing elegance, future-proofing everything, or "cleaning up" adjacent areas just because they are visible.
