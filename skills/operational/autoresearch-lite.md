# Title
autoresearch-lite

## Mission
Run tightly scoped, evidence-driven improvement loops on a small part of the system without turning the project into an uncontrolled research sandbox.

## When to use
Use this skill only when:
- the block is explicitly marked as experimental,
- the target is narrow and isolated,
- the acceptance metric is clear,
- rollback is easy,
- and the experiment does not touch critical business contracts.

Typical valid targets:
- prompt wording,
- scoring heuristics in non-critical sandboxed paths,
- copy/output phrasing,
- small selection rules,
- test improvements,
- documentation clarity,
- isolated helper behavior.

## When NOT to use
Do not use this skill for:
- persisted schema changes,
- critical endpoint contract changes,
- payment, legal, compliance or high-risk flows,
- external channel integrations,
- CRM or notification systems,
- broad refactors,
- multi-module redesign,
- anything that cannot be safely rolled back.

## Required checks before starting
1. Define the exact experimental target.
2. Define the single most important acceptance metric.
3. Define the maximum number of iterations allowed.
4. Define the files/modules allowed to change.
5. Define what is explicitly out of scope.
6. Confirm how rollback will work.
7. Confirm what validation will be run after each iteration.
8. Confirm that the experiment is isolated from critical flows.

## Required workflow
1. Restate the experiment in one paragraph.
2. Freeze the allowed scope:
   - files,
   - rules,
   - contracts,
   - max iterations.
3. Establish baseline behavior or baseline metric.
4. Make one small change at a time.
5. Run validation after each change.
6. Compare against the baseline.
7. Keep only changes that improve the defined metric or meaningfully reduce risk.
8. Revert or discard changes that do not clearly help.
9. End with a concise conclusion:
   - what improved,
   - what failed,
   - what remains unknown,
   - and whether further iteration is justified.

## Rules
- One experimental loop must have one clear target.
- Prefer one-file or one-surface experiments whenever possible.
- Do not run open-ended exploration.
- Do not silently expand scope mid-loop.
- Do not mix research goals with production hardening goals.
- Do not keep a change just because it is interesting.
- Do not treat "different" as "better".
- Do not exceed the predefined iteration cap without explicit approval.
- Every iteration must leave evidence:
  - test result,
  - metric result,
  - or clearly stated qualitative improvement.
- If the experiment does not show clear value quickly, stop.

## Validation standard
After each iteration, run the smallest meaningful validation available, such as:
- targeted tests,
- sandbox execution,
- contract checks,
- before/after output comparison,
- metric comparison,
- regression check.

## Output expectations
At the end of the loop, explicitly report:
- experimental target,
- baseline,
- iterations attempted,
- winning change if any,
- discarded changes,
- validation evidence,
- residual risks,
- follow-ups if justified.

## Non-goals
This skill is not for autonomous open-ended coding, broad research programs, speculative architecture, or uncontrolled self-improvement loops.
