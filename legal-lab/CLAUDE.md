# legal-lab/CLAUDE.md

Isolated legal-intelligence module. Global `.claude/CLAUDE.md` applies. This file adds local rules only.

## Boundary

- Do not import from `apps.api`, `trading_lab`, or `core`.
- Do not modify files outside `legal-lab/`.
- No shared-core extraction.

## Defaults

- Keep routes in single `cases.py` until it exceeds ~300 lines.
- No service layer until route logic justifies it.
- No update/delete endpoints without explicit approval.
- Event failures are logged and reported, not silent.

## Stop if

- New dependency needed
- Shared import from another module
- Schema grows beyond approved 7 entities + events table
- Feature creep toward CRM, workflow engine, or autonomous agents
