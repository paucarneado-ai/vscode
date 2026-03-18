# Prompt Templates — OpenClaw

Copy, fill brackets, use. Always read docs/briefs/guardrails.md.

---

## BUILD

```
Read docs/briefs/[brief].md and docs/briefs/guardrails.md before changing anything.

Task: Implement [feature name].

Goal: [one sentence on what success looks like]

Scope:
- [what to build]

Out of scope:
- [what NOT to build]
- [what NOT to refactor]

Frozen decisions to respect:
- [relevant rule from brief/guardrails]

Requirements:
- [requirement 1]
- [requirement 2]

Constraints:
- preserve current contracts unless [exception]
- no [constraint]

Tests required:
- [test 1]
- [test 2]

Definition of done:
- all tests passing
- runbook/docs updated if behavior changed
- deferred debt listed explicitly

Deliverables:
- exact files changed
- rationale
- tests passing
- explicit deferred debt
```

---

## HARDEN

```
Read docs/briefs/[brief].md and docs/briefs/guardrails.md before changing anything.

Task: Harden [module/surface] without expanding scope.

Already done: [recent changes providing context]

Required corrections:
1. [fix 1]
2. [fix 2]

Frozen decisions to respect:
- [relevant rule]

Out of scope:
- [what NOT to change]

Constraints:
- no scope expansion
- no new features
- preserve current behavior

Definition of done:
- all tests green
- no contract changes unless explicitly required

Deliverables:
- exact files changed
- what each fix prevents
- tests passing
- deferred debt if any
```

---

## AUDIT

```
Read docs/briefs/[brief].md before changing anything.

Task: Audit [area] for [risk type].

Goal: Find real problems, not theoretical ones.

Focus:
- [concern 1]
- [concern 2]

Out of scope:
- [what not to audit]

Deliver:
- current state map
- risks ranked by severity
- top 3 improvements by ROI
- what NOT to touch
- what is acceptable debt
```

---

## PATH DISCOVERY

```
Run pathway_discovery focused on [module area].

Focus:
- [structural concern 1]
- [structural concern 2]

Deliver:
- module snapshot
- flow map
- structural risks ranked
- clean insertion point for [next change]
- what NOT to refactor yet
```

---

## INTEGRATION

```
Read docs/briefs/[brief].md and docs/briefs/guardrails.md.

Task: Implement [integration name] ingestion into OpenClaw.

Target flow: [source] -> [transform] -> [OpenClaw endpoint]

Frozen decisions to respect:
- [e.g., n8n is translation layer, not OpenClaw]

Out of scope:
- [exclusion 1]

Deliverables:
- files changed
- payload contract
- field mapping
- tests passing
- runbook notes
- deferred debt
```

---

## MAINTENANCE

```
Read docs/briefs/maintenance_ops.md and deploy/ops/ scripts.

Task: [maintenance improvement]

Priority:
1. [highest ROI fix]
2. [second fix]

Constraints:
- no monitoring stack
- no CI/CD
- keep everything small

Deliverables:
- files changed
- what each improvement prevents
- VPS commands operator must run
- what remains manual
```

---

## BUGFIX

```
DELTA SINCE: [last known good state]
- [what broke]

CURRENT STATE:
- [symptom]

Task: Diagnose and fix [bug].

Scope: [narrow file/module]

Constraints:
- minimal fix only
- do not refactor surrounding code

Deliverables:
- root cause
- exact fix
- regression test added
- tests passing
```

---

## DOC / RUNBOOK

```
Read docs/briefs/[brief].md and current [doc file].

Task: Update [doc] to reflect [recent changes].

Changes to document:
- [change 1]
- [change 2]

Constraints:
- update only affected sections
- remove stale content
- keep concise

Deliverables:
- sections updated
- stale content removed
```
