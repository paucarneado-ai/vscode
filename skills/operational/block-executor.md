# Title
block-executor

## Mission
Execute medium and large implementation blocks in disciplined stages instead of ad-hoc coding, while preserving alignment with the master context and the current block contract.

## When to use
Use this skill when:
- the task affects multiple files,
- the task spans a full flow or feature slice,
- a new route, module, or integration is being added,
- or the block is large enough to benefit from internal structure.

## Required workflow
1. Read the master context and current block instructions.
2. Restate the block goal in precise terms.
3. Restate:
   - scope,
   - non-goals,
   - frozen constraints,
   - and acceptance criteria.
4. Identify dependencies, integration points, and likely risks.
5. Produce a short execution plan with the smallest coherent phases possible.
6. Implement phase by phase.
7. Run relevant tests and validation steps.
8. Validate in sandbox and/or Docker when applicable.
9. Summarize:
   - changes made,
   - validation evidence,
   - residual risks,
   - debt,
   - and follow-ups.

## Rules
- Do not jump straight into implementation before clarifying scope and constraints.
- Do not silently reinterpret the task to make it broader.
- Do not claim completion without validation evidence appropriate to the block.
- If the block reveals a contradiction with the master context, call it out explicitly before proceeding.
- Prefer the smallest complete implementation that satisfies the block.

## Output expectations
A completed block should leave:
- working implementation,
- relevant tests or validation evidence,
- concise change summary,
- explicit residual debt/follow-ups,
- and no silent scope expansion.

## Non-goals
This skill is not for speculative architecture, endless planning, or replacing concrete execution with narrative.
