# Decision Delta Log — OpenClaw

What changed, when, and why. Optimized for "catch me up since last time."
Read top-down. Newest first.

## What belongs here
- Contract changes (new/changed fields on API responses)
- Scoring/threshold changes
- Architecture changes (module extraction, new services, route restructuring)
- Security changes (auth, rate limiting, surface changes)
- Integration additions (new providers, new ingestion paths)

## What does NOT belong here
- Test-only changes
- Doc-only updates (unless they document a decision change)
- Internal refactors that don't change behavior or contracts
- Bug fixes (unless they change a contract or frozen decision)

## Entry format
```
## YYYY-MM-DD — Short title

**Changed:** [bullet list]
**Contract impact:** [additive / breaking / none]
**Why:** [one sentence]
```

---

## 2026-03-18 — Operational usefulness pass

**Changed:**
- LeadOperationalSummary now includes: `email`, `phone`, `priority_reason`
- Instructions changed from English generic to Spanish actionable
- `build_priority_reason()` added to actions.py — deterministic explanation of lead priority
- `_extract_phone()` added to operational.py — surfaces phone from structured notes

**Contract impact:** Additive fields only. Existing consumers unaffected.

**Why:** Operator could not act on queue items without clicking into each lead. Now contact info and reason are visible in list view.

---

## 2026-03-18 — Maintenance hardening

**Changed:**
- `check-staging.sh`: DB integrity, backup freshness, cron visibility, auth validation, disk space
- `backup-sqlite.sh`: 30-file retention, integrity pre-check
- `restore-sqlite.sh`: interactive restore with validation and pre-restore snapshot
- `smoke-intake.sh`: production safety guard (--production flag required)
- `verify-backup.sh`: validate backup recoverability without touching live DB
- Runbook: incident recovery procedures, Sentry validation commands

**Why:** No automated backup, no restore path, no operational checks beyond HTTP pings.

---

## 2026-03-18 — Rating threshold alignment

**Changed:** `get_rating()` thresholds from 50/75 to 40/60.

**Why:** Rating was misaligned with action thresholds (40/60) and summary buckets (40/60). Now all three use the same bands.

---

## 2026-03-18 — Lead scoring MVP

**Changed:** Scoring engine rewritten with commercial signals: phone (+10), source quality (+5-10), high-value types (+10), eslora (+10), price (+15), detail fields (+5 each), free-text (+5). Base lowered from 30 to 20.

**Why:** Previous scoring was a placeholder. No phone detection, no source differentiation, legacy form values not recognized.

---

## 2026-03-18 — Auth MVP + rate limiting

**Changed:**
- `auth.py`: X-API-Key header auth, fail-closed in production, dev bypass
- `ratelimit.py`: per-IP fixed-window rate limit on public intake (10/60s)
- Routes split: `router` (auth-protected) + `public_router` (rate-limited, no auth)

**Why:** All endpoints were open. No abuse guard on public intake.

---

## 2026-03-18 — Meta/n8n intake

**Changed:**
- Normalization extracted from routes to `services/intake.py` (normalize_web_intake, normalize_webhook_payload)
- Routes thinned: parse → normalize → create → respond
- Runbook: Meta/n8n integration section with payload contract

**Why:** Meta leads via n8n needed a clean webhook path. Inline normalization in routes would have caused sprawl.

---

## 2026-03-18 — Service layer extraction (4 iterations)

**Changed:**
- `services/operational.py`: read composition (actionable, pack, operational)
- `services/intake.py`: write + query (create_lead, query_leads, get_lead_by_id, etc.)
- `ACTION_PRIORITY` moved to `services/actions.py`
- `routes/leads.py` no longer imports db, scoring, actions, or leadpack directly
- `routes/internal.py` no longer imports from routes/leads

**Why:** routes/leads.py was a 400-line monolith with 7 fan-out. Known debt (routes→db) resolved.

---

## 2026-03-18 — pathway_discovery intermediate role classification

**Changed:** `intermediate_role` field added to long_path candidates (shared_composer / contract_translator / pass_through / unknown). Severity reduction for composition hubs.

**Why:** pathway_discovery was treating legitimate composition hubs as bottlenecks, generating false-positive escalations.

---

## Format for new entries

```
## YYYY-MM-DD — Short title

**Changed:** [bullet list of what changed]

**Contract impact:** [additive / breaking / none]

**Why:** [one sentence on the problem solved]
```
