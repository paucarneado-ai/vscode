# Title
integration-safety

## Mission
Protect compatibility, contracts, and shared logic integrity when implementing changes on top of an existing system.

## When to use
Use this skill when:
- adding a new entry point,
- modifying shared services,
- touching existing routes,
- changing output formats,
- or introducing new logic that should reuse current behavior.

## Required checks
1. Identify existing routes, services, and contracts affected by the block.
2. Identify where current logic can be reused cleanly.
3. Check whether the new implementation introduces:
   - duplicated logic,
   - parallel paths,
   - contract drift,
   - or backward-compatibility risk.
4. Run tests relevant to impacted flows.
5. Explicitly note any known divergence left in place temporarily.

## Rules
- Reuse existing business logic when possible instead of duplicating it.
- Do not introduce parallel logic paths unless clearly justified.
- Do not silently break existing endpoints or consumers.
- Preserve backward compatibility unless the block explicitly allows a breaking change.
- If a temporary divergence remains, record it as known divergence or debt.

## Output expectations
At the end of the block, explicitly state:
- what existing logic was reused,
- what contracts were preserved,
- what integration points were touched,
- and whether any compatibility debt remains.

## Non-goals
This skill is not for redesigning the whole architecture just because an integration point is imperfect.
