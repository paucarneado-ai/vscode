# Title
decision-log-updater

## Mission
Preserve operational memory after each meaningful block so that key decisions, divergences, debt, and follow-ups do not get lost in chat output.

## When to use
Use this skill after:
- meaningful implementation blocks,
- detection of contradictions between code and context,
- explicit deferral of work,
- discovery of technical debt,
- or freezing of a new decision.

## Required entries
Record concise, explicit entries for:
- newly frozen decisions,
- provisional assumptions,
- known divergences,
- accepted technical debt,
- deferred work,
- and follow-ups.

## Classification rules
Distinguish clearly between:
- Frozen decision: should govern future work unless explicitly changed.
- Provisional assumption: currently used but still open to revision.
- Known divergence: mismatch between intended model and current implementation.
- Technical debt: consciously accepted imperfection with future cost/risk.
- Follow-up: useful next step not included in the current block.

## Rules
- Do not hide important debt inside a generic summary.
- Do not leave important divergences only in transient chat output.
- Keep entries concise, operational, and reviewable.
- Do not inflate the log with vague future ideas that are not actionable.
- If a decision changes an earlier one, make that explicit.

## Output expectations
Each block should leave a clean memory trail showing:
- what is now frozen,
- what remains provisional,
- what mismatch exists,
- what was deferred,
- and what should happen next.

## Non-goals
This skill is not for writing long prose summaries or speculative product essays.
