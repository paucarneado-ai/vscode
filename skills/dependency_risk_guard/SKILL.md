# Dependency Risk Guard

## Mission
Challenge whether a new dependency should enter the project.

## When to use
Before adding any new package, library, or external tool to requirements, pyproject.toml, or imports.

## Procedure
1. State what the dependency does in one sentence.
2. Answer mandatory questions (all dependencies):
   - What stdlib or existing-code alternative exists?
   - How many lines of code would the alternative take?
   - Does it touch network, filesystem, or secrets?
3. Answer extended questions (runtime dependencies only):
   - Is it actively maintained? (last release, open issues)
   - What is its transitive dependency count?
   - What happens if it is abandoned in 6 months?
   - Does it require a C extension or system-level install?
4. Classify:
   - **reject**: stdlib or existing code covers it in <50 lines
   - **challenge**: possible but inconvenient without it — present tradeoff to operator
   - **accept**: genuinely hard to replicate, well-maintained, low risk
5. If reject or challenge: propose the alternative.
6. If accept: state the residual risk.

## Required output
- **Dependency**: name and version
- **Purpose**: one sentence
- **Alternative**: what exists without it
- **Classification**: reject / challenge / accept
- **Decision**: use it / do not use it / defer to operator
- **Residual risk**: if accepted
- **Approval needed**: yes/no

## Rules
- "It's popular" is not a justification.
- "It saves 10 lines" is not a justification if those 10 lines are simple.
- Every dependency is maintenance debt. The bar is: does it pay for itself?
- Test and dev dependencies get the same scrutiny on mandatory questions.

## Non-goals
Not for auditing existing dependencies. Not for version pinning strategy.
