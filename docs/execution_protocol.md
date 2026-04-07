# Execution Protocol

> Operational discipline layer for BUILD and HARDEN blocks.
> Templates live in `docs/work_templates.md`. This protocol governs how they are used.

---

## 1. Purpose

Prevent drift, scope creep, false closures, and unclassified work.
Every non-trivial change goes through a protocol block. No exceptions.

---

## 2. When a block must use protocol

Any change that meets at least one:
- touches more than 1 file
- adds or removes a field, endpoint, or query param
- changes observable behavior
- requires a judgment call about scope

Only trivial edits with no scope, contract, or behavior ambiguity may skip protocol. If in doubt, use protocol.

---

## 3. Preflight checklist

Before opening any block:

1. Classify: is this BUILD or HARDEN? State it. If classification is unclear, inspect first and classify before editing. Do not guess.
2. If BUILD looks like it might fix something broken, reclassify as HARDEN.
3. If HARDEN requires new structure, new files, or new contracts, stop — reclassify as BUILD or ask for approval.
4. Fill the appropriate template from `docs/work_templates.md` before editing any file.
5. State EXPECTED FILES and DO NOT TOUCH before editing any file.
6. State what would make you stop the block.
7. State what evidence will prove completion.

---

## 4. BUILD execution rule

- The minimum acceptable implementation is a ceiling, not a floor.
- If the code works and satisfies DONE WHEN, stop. Do not improve, extend, or "complete" it further.
- Every file touched must be declared in EXPECTED FILES. Touching an undeclared file requires pausing and stating why.
- Do not add fields, params, schemas, branches, error handling, or behavior not required by GOAL or DONE WHEN.
- "Useful" is not a justification. Only "required by DONE WHEN" is a justification.

---

## 5. HARDEN execution rule

- One bug, one fix path. Do not bundle.
- State root-cause hypothesis before editing. If the hypothesis is weak, inspect more — do not edit speculatively.
- The smallest correct change is the ceiling.
- If the fix changes observable behavior beyond the stated bug, stop and surface it.
- If the fix requires new files, new schemas, or new endpoints, it is not HARDEN. Reclassify as BUILD.
- Do not clean up adjacent code. Do not refactor nearby logic. Do not improve formatting outside the fix.

---

## 6. Approval gate

Pause and ask before any of these, regardless of block type:

- Touching a file listed in DO NOT TOUCH
- Exceeding declared EXPECTED FILES
- Adding a dependency
- Changing a schema, contract, or response shape not declared in SCOPE
- The implementation exceeding the declared minimum

Do not assume approval from a previous block carries forward.

---

## 7. Closure gate

A block is not closed until all of these are true:

- Every claim in DONE WHEN has specific evidence (test output, endpoint response, or behavioral proof).
- "Code was written" is not evidence. "Test passed" is evidence only when the test proves the claimed scope or fix.
- The final response uses the template closure format (Changed / Verified / Not verified / Left untouched / Follow-up & debt).
- Any file touched outside EXPECTED FILES is explicitly noted and justified.
- Any deviation from the original plan is explicitly noted.

---

## 8. When to force a second-pass HARDEN

Run a HARDEN review on a completed BUILD when any of these is true:

- The BUILD touched 3+ files
- The BUILD added a new contract (endpoint, schema, response shape)
- The BUILD required judgment calls about scope
- The operator requests it

The HARDEN review must evaluate: contract weight, speculative fields, missing input validation, consistency with existing patterns.

---

## 9. Common failure modes

| Failure | Detection signal | Countermeasure |
|---|---|---|
| Scope creep | Touching undeclared files, adding unrequested fields | Stop. Check against EXPECTED FILES and DONE WHEN |
| Enrichment bias | "While I'm here" additions, extra error handling, bonus params | Delete the extra. If unsure, ask |
| HARDEN → BUILD drift | Fix requires new schema, new endpoint, or new file | Reclassify. Do not continue as HARDEN |
| Weak hypothesis | Editing before stating root cause, or root cause is vague | Stop editing. Inspect more. State a falsifiable hypothesis |
| False closure | "Verified" without test output, "Done" without DONE WHEN evidence | Reopen. Run the actual verification |
| Cosmetic side quest | Reformatting, renaming, adding types to untouched code | Revert. Only touch code required by the fix |
