# Title
automation-consumer-guard

## Mission
Protect internal automation-consumption work from expanding into a full orchestration system, external-channel integration, or unnecessary architecture before the MVP truly requires it.

## When to use
Use this skill when a block:
- consumes operational lead outputs for internal action,
- prepares leads for internal automation,
- introduces eligibility/actionability rules,
- or creates a new internal contract or endpoint meant for machine-to-machine consumption.

## Required checks
Before implementation:
1. Identify the exact operational problem being solved.
2. Identify which existing contract or output is the best base:
   - pack,
   - delivery,
   - operational contract,
   - or a minimal projection of one of them.
3. Confirm whether the block really needs:
   - a new endpoint,
   - a helper,
   - or only a projection/reuse of existing logic.
4. Define the smallest useful rule set for deciding whether a lead is actionable.
5. Confirm that no external channel or orchestration engine is being introduced implicitly.

During implementation:
6. Keep actionability rules explicit, small, and easy to test.
7. Reuse existing lead outputs and services instead of creating a second decision system.
8. Keep machine-consumable outputs flat or trivially consumable.
9. Record anything that would require a richer future automation layer as follow-up, not inline scope.

## Rules
- Do not turn an internal automation-consumption block into:
  - a CRM integration,
  - a notification platform,
  - a worker/queue system,
  - a scheduler,
  - or a generic orchestration engine.
- Do not introduce new persisted states unless explicitly required by the block.
- Do not invent actionability signals that the current system does not actually have.
- Do not duplicate scoring logic inside automation-consumption logic.
- Do not create multiple overlapping machine-consumable contracts unless there is a clear reason.
- Prefer one narrow, stable, reusable contract over several half-overlapping outputs.
- If a new endpoint is added, it must be justified as the smallest practical API-first solution.

## Output expectations
At the end of the block, explicitly state:
- what the internal automation-consumption contract is,
- what makes a lead actionable in the current MVP,
- what existing structures were reused,
- what was intentionally not built,
- and what future automation work remains out of scope.

## Non-goals
This skill is not for building a full automation platform, messaging system, queue architecture, or production-grade orchestration framework.
