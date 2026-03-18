# Delta-First Prompting — OpenClaw Convention

## Problem
Starting each conversation with "Read everything" wastes context on unchanged state.

## Format

```
DELTA SINCE: [last block name or date]
- [change 1]
- [change 2]

CURRENT STATE:
- [key facts needed for this task]

FROZEN DECISIONS TO RESPECT:
- [relevant frozen rule from brief/guardrails]

TASK: [one sentence]

SCOPE: [files/modules affected]

OUT OF SCOPE: [what NOT to touch]

READ FIRST: [brief + specific files]
```

## Example

```
DELTA SINCE: scoring MVP
- Rating thresholds aligned to 40/60
- priority_reason field added to LeadOperationalSummary
- Instructions changed to Spanish

CURRENT STATE:
- 206 API tests passing
- Queue sort: alert DESC → action priority → score DESC
- No recency tie-breaking yet

FROZEN DECISIONS TO RESPECT:
- Do not change scoring thresholds without approval
- Rating/action bands must stay aligned at 40/60

TASK: Add created_at as tie-breaker in queue sort

SCOPE: apps/api/routes/internal.py

OUT OF SCOPE: scoring changes, worklist grouping, new endpoints

READ FIRST: docs/briefs/lead_ops.md, apps/api/routes/internal.py
```

## When to use
- Continuation of a previous block
- Narrow task on a specific module
- Bug fix with known context

## When NOT to use
- New feature touching multiple modules (read briefs + more context)
- Architecture decisions (need full context master)
- First work in a new area (start with the brief)
