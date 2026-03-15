# Work Templates

> Operational templates for launching BUILD and HARDEN blocks with Claude Code.
> These are protocols, not suggestions. Use them to reduce scope creep, side quests, hidden refactors, and superficial validation.

---

## BUILD quick

```
MODE: BUILD
OPERATOR:
GOAL:
SCOPE:
OUT OF SCOPE:
EXPECTED FILES:
DO NOT TOUCH:
CONSTRAINTS:
APPROVAL TRIGGERS:
DONE WHEN:

Before editing:
- give a short plan
- name expected files
- state minimum acceptable implementation

Rules:
- if a smaller implementation satisfies GOAL and DONE WHEN, choose it
- do not add fields, checks, branches, or behavior not required by DONE WHEN
- do not add extras that feel useful but are not required by GOAL or DONE WHEN
- treat minimum acceptable implementation as a ceiling unless approval is given

Final response:
- Changed
- Verified
- Not verified
- Left untouched
- Follow-up / debt
```

---

## HARDEN quick

```
MODE: HARDEN
OPERATOR:
GOAL:
SCOPE:
OUT OF SCOPE:
EXPECTED FILES:
DO NOT TOUCH:
CONSTRAINTS:
APPROVAL TRIGGERS:
DONE WHEN:

Before editing:
- state root-cause hypothesis
- state why this is the most likely local cause
- give a short plan
- name expected files
- state verification target

Rules:
- one bug, one fix path
- fix the cause, not the symptom
- if root-cause hypothesis is too weak to define a minimal fix, inspect more before editing
- do not clean up adjacent issues unless explicitly approved
- if the fix changes behavior beyond the stated bug, stop and surface it
- treat smallest correct change as a ceiling unless approval is given

Final response:
- Changed
- Verified
- Not verified
- Left untouched
- Follow-up / debt
```

---

## BUILD elite

```
=== BLOCK HEADER ===
MODE: BUILD (elite)
OPERATOR:
GOAL:
RISK LEVEL: low | medium | high

First: confirm this is truly BUILD. If it is misclassified, say so before editing.
If risk is medium or high, name the main failure mode before editing.

=== EXECUTION CONTRACT ===
SCOPE:
OUT OF SCOPE:
EXPECTED FILES:
DO NOT TOUCH:
CONSTRAINTS:
MINIMUM ACCEPTABLE IMPLEMENTATION:

CHANGE BUDGET:
- files touched: max [N]
- new files: max [N]
- scope expansion: none unless approved

APPROVAL TRIGGERS:

Rules:
- bias toward the thinnest useful contract
- if a smaller implementation satisfies GOAL and DONE WHEN, choose it
- do not add fields, checks, branches, or behavior not required by DONE WHEN
- do not add extras that feel useful but are not required by GOAL or DONE WHEN
- treat minimum acceptable implementation as a ceiling unless approval is given

Phase 1: inspect and plan only. Do not edit until you state:
- short plan
- expected files
- main risk
- minimum acceptable implementation
- verification target
- likely approval triggers

=== STOP CONDITIONS ===
Stop and re-align if:
- scope grows beyond declared budget
- a new dependency or contract change appears
- the approach requires touching DO NOT TOUCH areas
- the implementation exceeds the declared minimum without approval
- [task-specific condition]

=== CLOSURE CONTRACT ===
DONE WHEN:

Verification must prove the delivered scope, not just nearby behavior.

Final response:
- Changed
- Verified
- Not verified
- Left untouched
- Follow-up / debt
- Approval needed [yes/no]
```

---

## HARDEN elite

```
=== BLOCK HEADER ===
MODE: HARDEN (elite)
OPERATOR:
GOAL:
RISK LEVEL: low | medium | high

First: confirm this is truly HARDEN. If it looks like BUILD, say so before editing.
If risk is medium or high, name the main failure mode before editing.

=== EXECUTION CONTRACT ===
SCOPE:
OUT OF SCOPE:
EXPECTED FILES:
DO NOT TOUCH:
CONSTRAINTS:
ROOT-CAUSE HYPOTHESIS:

CHANGE BUDGET:
- files touched: max [N]
- new files: 0
- scope expansion: none unless approved

APPROVAL TRIGGERS:

Rules:
- one bug, one fix path
- fix the cause, not the symptom
- if root-cause hypothesis is too weak to define a minimal fix, inspect more before editing
- do not clean up adjacent issues unless explicitly approved
- if the fix changes behavior beyond the stated bug, stop and surface it
- treat smallest correct change as a ceiling unless approval is given

Phase 1: inspect and plan only. Do not edit until you state:
- root-cause hypothesis
- why this is the best local fix target
- what result would falsify the hypothesis
- short plan
- expected files
- verification target
- likely approval triggers

=== STOP CONDITIONS ===
Stop and re-align if:
- the fix requires changing more than the declared scope
- expected files or areas exceed the declared budget
- a contract or schema change is needed
- the fix turns into a rewrite
- the fix changes observable behavior beyond the stated bug
- the problem is no longer local and needs reclassification as BUILD
- [task-specific condition]

=== CLOSURE CONTRACT ===
DONE WHEN:

Verification must test the claimed fix, not just general suite health.

Final response:
- Changed
- Verified
- Not verified
- Left untouched
- Follow-up / debt
- Root cause confirmed [yes/no/partial]
- Approval needed [yes/no]
```

---

## When to use each

Quick = default for bounded, low-ambiguity work in one module.

Elite = use when any of these is true:
- new module or integration
- touches more than 3 files or more than 1 module
- ambiguous scope or acceptance criteria
- high-impact area
- likely to span more than one conversation
- human explicitly asks for elite

When in doubt, use elite.
