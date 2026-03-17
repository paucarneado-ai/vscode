# tasks/todo.md

## Active Task
Task: HARDEN — Demo Intake Defensive Markers

## Objective
Add anti-indexing, anti-caching, visible demo-only copy, and safe response headers to `/demo/intake`. Protect with one test.

## Plan
- [x] Add `<meta name="robots" content="noindex,nofollow">` to HTML head
- [x] Add visible "Internal demo only — not a production surface" footer
- [x] Add `Cache-Control: no-store` and `X-Content-Type-Options: nosniff` response headers
- [x] Add `test_demo_intake_defensive_markers` asserting all markers
- [x] Run tests — 283 passed

## Review
### Hardened
- Anti-indexing: `noindex,nofollow` meta tag in HTML head
- Anti-caching: `Cache-Control: no-store` response header
- MIME-sniffing: `X-Content-Type-Options: nosniff` response header
- Visible copy: footer text "Internal demo only — not a production surface"
- Test: `test_demo_intake_defensive_markers` guards all four markers against drift

### Verified
- 283 tests pass (0 failures)
- All four markers asserted in test (meta tags, visible copy, both headers)

### Not verified
- N/A — all changes are testable and tested

### Left untouched
- CSP: inline script/style would require `unsafe-inline`, cost exceeds benefit for disposable demo
- X-Frame-Options: no XSS vector (textContent), same-origin, no sensitive data
- Referrer-Policy: no outbound links or external resources

### Residual debt
- None introduced

### Approval needed
No
