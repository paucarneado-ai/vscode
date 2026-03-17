# Complexity Killer

## Mission
Shrink the solution before implementing it.

## When to use
Before writing code for any non-trivial block.
Especially when the first instinct involves multiple files, new abstractions, or new endpoints.

## Procedure
1. Write the solution in one sentence.
2. Count: files touched, new functions, new schemas, new endpoints.
3. For each new thing, ask: can this be eliminated by reusing something that exists?
4. For each file touched, ask: can this file be removed from the plan?
5. If the solution has more than one new abstraction, justify each independently.
6. If a simpler version solves 90% of the problem, propose that version first.
7. State the final reduced plan before editing.

## Required output
Before any implementation, state:
- **Original scope**: files, functions, schemas, endpoints (counts)
- **Reduced scope**: same counts after reduction
- **What was cut**: each eliminated item and why
- **What was kept despite complexity**: item, what business value it protects

## Rules
- Three similar lines are cheaper than one premature abstraction.
- A helper for one call site is not a helper.
- "Might need it later" is not a reason.
- If reduction removes business value, state what value is lost and why the complexity is justified. Otherwise cut.
- If further reduction would make the solution unable to meet the business goal, stop reducing and state why.

## Non-goals
Not for blocking necessary complexity. Not for making things ugly on purpose.
