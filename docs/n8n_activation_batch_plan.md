# n8n Activation Batch Plan — 3 Pending Workflows

One-time plan for activating all 3 pending workflows in a single session.
Execute when n8n access is available. Estimated time: 30-45 minutes.

---

## A. Recommended Activation Order

| Order | Workflow | Justification |
|-------|----------|---------------|
| **1st** | **New Lead Notification** | Highest monetization impact — reduces lead reaction time from 24h to ~5min. Most complex activation (watermark seed + multi-lead test). If this fails, the other two still work independently. |
| **2nd** | **Sentinel Health Alert** | Operational safety net — detects system degradation. Activating it second means it monitors the system while the remaining workflow is set up. Has state (fingerprint) that needs a seed verification. |
| **3rd** | **Follow-up Action Digest** | Incremental improvement over existing daily snapshot. Stateless (simplest activation). Lowest blast radius if delayed. |

**Rationale:**
- Lead notification directly speeds up monetization (operator contacts leads faster)
- Sentinel protects the system (detect if lead intake or event spine breaks)
- Follow-up digest is additive (operator already sees follow-ups in morning snapshot)
- All 3 share the same credential/config pattern, so setup gets faster with each workflow

---

## B. Shared Setup (do once, before any workflow)

These steps apply to all 3 workflows. Do them once at the start of the session.

### B1. Confirm n8n runtime

```bash
# From the n8n container (via EasyPanel shell or docker exec)
node --version
```

**Required:** v18.0.0 or higher. All 3 workflows use `fetch()` in Code nodes.
**If below v18:** Stop. Upgrade n8n before proceeding.

### B2. Determine API_BASE

The daily-ops-snapshot is already deployed. Check which base URL it uses:

1. Open **daily-ops-snapshot** workflow in n8n
2. Open any HTTP Request node (e.g., "Fetch Ops Snapshot")
3. Note the URL (e.g., `http://localhost:8000/internal/ops/snapshot`)
4. Extract the base: everything before `/internal/...`

**Expected result:** One of:
- `http://localhost:8000` (co-located, no proxy)
- `http://openclaw-api:8000` (Docker network name)
- `http://76.13.48.227:8080/api` (via Caddy proxy)

**Record:** `API_BASE = _______________`

**Critical path adjustment:** If API_BASE includes `/api` (Caddy proxy path), then:
- New Lead Notification calls `/leads?limit=...` → must become `/api/leads?limit=...`
- Follow-up Digest calls `/internal/followup-automation` → must become `/api/internal/followup-automation`
- Sentinel calls `/internal/sentinel` → must become `/api/internal/sentinel`

The Code node paths are hardcoded inside the `apiFetch()` calls. If the base includes `/api`, either:
- Set `API_BASE = http://76.13.48.227:8080` and edit each fetch path to add `/api` prefix, OR
- Set `API_BASE = http://76.13.48.227:8080/api` and leave paths as-is (the `/api` prefix will be prepended automatically)

**Test from n8n container:**
```bash
curl -s http://API_BASE/health | head -20
```
If this returns `{"status":"ok",...}`, the base is correct.

### B3. Confirm API_KEY

Same key used by the daily-ops-snapshot's Header Auth credential.

1. In n8n, go to **Credentials** → find the Header Auth credential used by daily-ops-snapshot
2. Note the API key value

**Record:** `API_KEY = _______________`

### B4. Confirm Telegram credential

1. In n8n, go to **Credentials** → find `OpenClaw Telegram Bot` (or whatever the daily-ops-snapshot uses)
2. Note the credential name and Chat ID used in the daily-ops-snapshot's Telegram node

**Record:**
- Telegram credential name: `_______________`
- Chat ID: `_______________`

### B5. Quick API smoke test

Before importing any workflow, verify the 4 endpoints all respond:

```bash
# From n8n container or VPS
API_BASE="http://YOUR_BASE"
API_KEY="YOUR_KEY"

curl -s -H "X-API-Key: $API_KEY" "$API_BASE/leads?limit=1" | head -5
curl -s -H "X-API-Key: $API_KEY" "$API_BASE/internal/followup-automation" | head -5
curl -s -H "X-API-Key: $API_KEY" "$API_BASE/internal/sentinel" | head -5
curl -s "$API_BASE/health"
```

All 4 must return valid JSON. If any returns connection refused / 401 / 404, fix before proceeding.

---

## C. Per-Workflow Activation

### Workflow 1: New Lead Notification

**Import:**
1. Workflows → Import from File → `new-lead-notification.json`
2. Verify 4 nodes: Poll Every 5 Minutes, Detect & Prepare, Send to Telegram, Update Watermark

**Configure:**
1. Open **Detect & Prepare** → set `API_BASE` and `API_KEY` (from B2/B3)
2. If API_BASE uses `/api` prefix: also update the 3 fetch paths in the code:
   - `/leads?limit=` → `/api/leads?limit=`
   - `/leads/${lead.id}/pack` → `/api/leads/${lead.id}/pack`
3. Open **Send to Telegram** → set Chat ID (from B4), select Telegram credential

**Test (5 scenarios, execute manually each time):**

| # | Scenario | Action | Expected | Evidence |
|---|----------|--------|----------|----------|
| 1 | First-run seed | Execute workflow | 0 items, no Telegram, static data shows `lastSeenId` | Check Workflow Settings → Static Data |
| 2 | Repeat, no new leads | Execute again | 0 items, no Telegram | |
| 3 | One new lead | Create lead via `POST /leads/webhook/smoke-test`, then execute | 1 Telegram message with correct content | Screenshot/note message |
| 4 | Multiple leads | Create 3 leads, execute | 3 Telegram messages in chronological order | |
| 5 | Duplicate prevention | Execute without new leads | 0 items, no Telegram | |

**Test lead creation command:**
```bash
curl -X POST http://API_BASE/leads/webhook/smoke-test \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"name":"Notif Test","email":"notif-test-1@openclaw-ops.internal","notes":"Tipo: Velero\nEslora: 12m\nMarca: Beneteau\nTelefono: +34600999888"}'
```

**Activate:** Toggle workflow to Active.

**Post-activation check:** Wait 5 minutes. If no new real leads arrived, no message should be sent. If a message IS sent unexpectedly, deactivate and check watermark state.

**Closure criteria:**
- [ ] Import succeeded
- [ ] First-run seed was silent (no flood)
- [ ] Repeat run suppressed duplicates
- [ ] One new lead sent exactly one message
- [ ] Multiple leads sent correct count in order
- [ ] Post-batch repeat sent nothing
- [ ] Schedule activated, no spurious messages in first cycle

---

### Workflow 2: Sentinel Health Alert

**Import:**
1. Workflows → Import from File → `sentinel-health-alert.json`
2. Verify 4 nodes: Poll Every 15 Minutes, Fetch & Evaluate, Send to Telegram, Update State

**Configure:**
1. Open **Fetch & Evaluate** → set `API_BASE` and `API_KEY`
2. If API_BASE uses `/api` prefix: update `/internal/sentinel` → `/api/internal/sentinel`
3. Open **Send to Telegram** → set Chat ID, select Telegram credential

**Test (4 scenarios):**

| # | Scenario | Action | Expected | Evidence |
|---|----------|--------|----------|----------|
| 1 | Healthy system | Execute workflow | If sentinel returns `ok`: 0 items, no Telegram. If sentinel returns non-ok: 1 alert message (this is correct behavior for first run) | Check node output |
| 2 | Repeat same state | Execute again within minutes | 0 items, no Telegram (fingerprint unchanged, cooldown not expired) | |
| 3 | Recovery (if system was non-ok) | Resolve the issue, execute | Recovery message ("Sistema recuperado") | |
| 4 | State persistence | Check static data shows `lastFingerprint`, `lastAlertedAt` | Values present and correct | Workflow Settings → Static Data |

**Note:** Unlike the new-lead notification, sentinel testing does not require creating test data. The sentinel endpoint returns whatever the current system state is. If the system is healthy, the first run will be a silent no-op (fingerprint stored as `ok|`). If the system has findings, the first run will send a legitimate alert.

**Activate:** Toggle workflow to Active.

**Post-activation check:** Wait 15 minutes. If system is healthy, no message should arrive. If a message arrives, it's a real sentinel finding — verify it's legitimate before dismissing.

**Closure criteria:**
- [ ] Import succeeded
- [ ] First run produced correct behavior (silent if ok, alert if findings)
- [ ] Repeat run suppressed duplicate (same fingerprint)
- [ ] Fingerprint stored in static data
- [ ] Schedule activated, no spurious messages

---

### Workflow 3: Follow-up Action Digest

**Import:**
1. Workflows → Import from File → `followup-digest.json`
2. Verify 3 nodes: Schedule (Daily 14:00), Fetch & Format, Send to Telegram

**Configure:**
1. Open **Fetch & Format** → set `API_BASE` and `API_KEY`
2. If API_BASE uses `/api` prefix: update `/internal/followup-automation` → `/api/internal/followup-automation`
3. Open **Send to Telegram** → set Chat ID, select Telegram credential

**Test (3 scenarios):**

| # | Scenario | Action | Expected | Evidence |
|---|----------|--------|----------|----------|
| 1 | With actionable follow-ups | Execute manually (on a weekday) | Telegram message with tier-grouped leads + suggested messages | Screenshot/note message |
| 2 | No actionable follow-ups | If all follow-up leads are recently_contacted, or none exist | 0 items, no Telegram | |
| 3 | Weekend guard | If testing on weekend: execute | 0 items, no Telegram (guard kicks in) | |

**Note:** This workflow is stateless — no seed required, no persistence to verify. Testing is simpler than the other two. If follow-up candidates exist in the system, scenario 1 will produce a message. If not, scenario 2 is the expected first-run behavior.

**Activate:** Toggle workflow to Active.

**Post-activation check:** The workflow fires at 14:00 daily. If activated before 14:00, it will fire same day. If after 14:00, it fires the next day.

**Closure criteria:**
- [ ] Import succeeded
- [ ] Manual execution produced correct message (or correctly sent nothing)
- [ ] Weekend guard verified (if testable)
- [ ] Schedule activated

---

## D. Likely Failure Points

| # | Failure | Symptom | Affects | Fix |
|---|---------|---------|---------|-----|
| 1 | **Wrong API_BASE** | `fetch failed` or `connection refused` in Code node | All 3 | Test with `curl` from n8n container first (step B5) |
| 2 | **Missing `/api` prefix** | `404 Not Found` from API calls | All 3 if using Caddy proxy | Add `/api` prefix to fetch paths OR include `/api` in API_BASE |
| 3 | **Wrong API_KEY** | `401` or `403` from API calls | All 3 | Copy exact key from daily-ops-snapshot's Header Auth credential |
| 4 | **fetch() not available** | `fetch is not defined` error in Code node | All 3 | n8n Node.js < 18. Upgrade n8n. |
| 5 | **Telegram credential not linked** | Telegram node shows "no credential" error | All 3 | Select existing credential in dropdown (same as daily-ops-snapshot) |
| 6 | **Wrong Chat ID** | Telegram sends to wrong chat or fails | All 3 | Copy exact Chat ID from daily-ops-snapshot Telegram node |
| 7 | **Watermark seeds with flood** | First run of new-lead sends all historical leads | New Lead only | Should not happen (code seeds silently). If it does: deactivate, clear static data, check code |
| 8 | **Sentinel alerts on healthy system** | First run sends alert when system is actually ok | Sentinel only | Check node output — if sentinel returns non-ok findings, the alert is legitimate |
| 9 | **Follow-up fires on weekend** | Message arrives on Saturday/Sunday | Followup Digest only | Weekend guard is in Code node. If it fires on weekend, check n8n timezone setting (must be Europe/Madrid) |
| 10 | **Schedule fires immediately on activation** | Toggling Active sends message right away | All 3 | n8n may execute immediately on activation depending on schedule. This is normal — not a bug. If unwanted, activate during a quiet period |

---

## E. Closure Criteria Summary

| Workflow | Closed when | Key evidence |
|----------|-------------|--------------|
| **New Lead Notification** | Seed silent + repeat suppressed + 1 lead = 1 msg + 3 leads = 3 msgs + post-batch silent + schedule active | Telegram screenshots + static data showing lastSeenId |
| **Sentinel Health Alert** | First run correct (ok=silent, non-ok=alert) + repeat suppressed + fingerprint stored + schedule active | Telegram screenshot (if alert) + static data showing lastFingerprint |
| **Follow-up Action Digest** | Manual execution correct (message or silent depending on data) + schedule active | Telegram screenshot (if follow-ups exist) |

---

## Quick Reference Card

**Shared values (fill once, use in all 3):**

```
API_BASE:  _______________
API_KEY:   _______________
Chat ID:   _______________
TG Cred:   _______________
```

**Per-workflow Code node edits:**

| Workflow | Code node name | Lines to edit |
|----------|---------------|---------------|
| New Lead Notification | Detect & Prepare | `API_BASE`, `API_KEY` (+ path prefix if needed) |
| Sentinel Health Alert | Fetch & Evaluate | `API_BASE`, `API_KEY` (+ path prefix if needed) |
| Follow-up Action Digest | Fetch & Format | `API_BASE`, `API_KEY` (+ path prefix if needed) |

**Import order:** New Lead → Sentinel → Follow-up Digest
**Total CONFIGURE_ME replacements:** 3 per workflow (API_BASE, API_KEY, Chat ID) = 9 total + 3 credential selections
