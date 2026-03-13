# Title
skill-builder-openclaw

## Mission
Create, tighten, or audit Claude Code skills with a bias toward usefulness, low overhead, clear triggers, hard guardrails, and real project value.

## When to use
Use this skill when:
- creating a new skill,
- shortening or hardening an existing skill,
- auditing whether a skill is too vague, too bloated, or too weak,
- deciding whether a skill should exist at all,
- converting a messy workflow into a reusable skill.

## Core principle
A skill must earn its existence.

Do not create or keep a skill unless it does at least one of these:
- reduces repeated prompting,
- reduces implementation errors,
- protects scope or quality,
- improves consistency of outputs,
- captures a reusable workflow,
- or meaningfully lowers cognitive load.

If it does none of these, do not build it.

## Modes

### Mode 1 — Build Fast
Use for small, practical, low-risk skills.

Goal:
Create a usable skill quickly with only the minimum required structure.

Required discovery:
1. What problem does the skill solve?
2. What should trigger it?
3. What inputs does it need?
4. What output should it produce?
5. What must it NOT do?

If these 5 are clear, build immediately.
Do not force a long discovery interview for a simple skill.

### Mode 2 — Build Deep
Use for larger or more reusable skills.

Use this mode only when the skill:
- has multiple steps,
- has dependencies,
- has side effects,
- needs supporting files,
- or is likely to be reused heavily.

Required discovery:
1. Goal
2. Trigger phrases
3. Invocation mode:
   - slash command,
   - natural language,
   - or both
4. Inputs
5. Outputs
6. Dependencies
7. Step-by-step workflow
8. Guardrails
9. Failure modes
10. Acceptance test

Only ask for missing information. Do not re-ask what is already known.

### Mode 3 — Audit
Use when reviewing an existing skill.

Audit questions:
1. Does this skill clearly deserve to exist?
2. Is the trigger description strong enough to activate reliably?
3. Is the workflow specific and actionable?
4. Is the output format clear?
5. Are file paths, dependencies, and guardrails explicit?
6. Is the skill too long?
7. Is it duplicating another skill or CLAUDE.md?
8. Is it overengineered for the actual task?
9. Does it need to be split, shortened, or deleted?

If the honest answer is "this skill is bloated, redundant, or weak," say so directly.

## Skill type decision
Choose explicitly between:

- **Task skill** — tells Claude how to perform a repeatable workflow
- **Reference skill** — gives Claude reusable project knowledge or constraints

Do not blur the two unless there is a very good reason.

## Build rules

### 1. Keep it tight
- Prefer shorter skills over long tutorial-style skills.
- Do not include explanations the operator already knows.
- Do not turn a skill into a course or reference manual unless that is the actual purpose.

### 2. Frontmatter discipline
Only use frontmatter fields that are actually needed.

Possible fields:
- `name`
- `description`
- `argument-hint`
- `disable-model-invocation`
- `context`
- `model`
- `allowed-tools`

Rules:
- Do not add optional fields just because they exist.
- If the skill has side effects, file generation, API calls, or cost risk, strongly consider `disable-model-invocation: true`.
- If the skill accepts arguments, include `argument-hint`.
- The `description` must use phrases a human would naturally say.

### 3. Content structure
Default structure for most skills:

1. Mission
2. When to use
3. Inputs
4. Workflow
5. Output expectations
6. Rules / Guardrails
7. Non-goals

Only add more sections if they materially improve reliability.

### 4. Specificity over abstraction
- Every workflow step must be actionable.
- Avoid vague phrases like "handle appropriately" or "use judgment" unless bounded by explicit rules.
- Specify file paths, outputs, and decision points.

### 5. Guardrails matter
A good skill must say:
- what it should not touch,
- what it should not assume,
- what it must validate,
- and when it must stop rather than improvise.

### 6. Avoid skill bloat
A skill is too big if:
- it tries to cover multiple unrelated workflows,
- it repeats extensive reference material better stored elsewhere,
- it teaches concepts instead of guiding execution,
- or it becomes harder to use than the original manual prompting.

If too big:
- split it,
- shorten it,
- or move reference material to supporting files.

## Output format for new skills
When building a new skill, produce:

1. a short rationale for why the skill should exist,
2. chosen skill type,
3. frontmatter,
4. final skill content,
5. any supporting file recommendations,
6. a short test plan.

## Output format for audits
When auditing an existing skill, produce:

## Audit Verdict
- **Keep / Tighten / Split / Delete**

## Why
- [direct explanation]

## Problems Found
- [bullets]

## Recommended Fix
- [specific changes]

## Revised Skill
- [only if revision is requested]

## Hard rules for this meta-skill
- Do not create a skill that duplicates an existing one without strong justification.
- Do not overdesign a skill for a workflow that happens rarely.
- Do not force "deep discovery" on simple operational skills.
- Do not hide weak skill quality behind polite language.
- Do not optimize for elegance over usefulness.
- If a normal prompt is better than a skill, say so.

## Test standard
Before considering a skill acceptable, check:
1. Could a teammate trigger it from the description?
2. Would Claude know what to do step by step?
3. Is the output shape clear?
4. Are the boundaries explicit?
5. Is the skill short enough to stay sharp?
6. Does it reduce future friction?

If not, it is not ready.

## Non-goals
This skill is not for teaching the full theory of Claude Code skills, reproducing long official documentation, or turning every workflow into a skill.
