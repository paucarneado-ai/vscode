# n8n Sentinel Health Alert — Runbook

## What this workflow does

Polls the OpenClaw Sentinel endpoint every 15 minutes and sends a Telegram alert when operational health degrades. Uses a deterministic fingerprint to distinguish meaningful state changes from noise. Sends a recovery message when health returns to normal.

**Workflow file:** `deploy/n8n/sentinel-health-alert.json`

## Sentinel checks covered

The `/internal/sentinel` endpoint runs 3 checks:

| Check | Surface | Severities | What it detects |
|-------|---------|------------|-----------------|
| `stale_claims` | dispatch | low, medium | Claims older than 24h (medium if >3, low if ≤3) |
| `source_needs_attention` | source-actions | low | Sources with `recommendation=review` and sufficient data |
| `event_spine_silent` | events | medium, high | HIGH: leads exist but zero events ever. MEDIUM: recent leads but no recent events |

**Status derivation:** `alert` if any HIGH finding, `watch` if any MEDIUM, `ok` otherwise.

## Fingerprint-based noise control

The workflow does **not** simply alert on every non-ok poll. It builds a deterministic fingerprint from the actual condition:

```
ok|                                        ← healthy
watch|stale_claims                         ← one watch-level issue
watch|event_spine_silent                   ← different watch-level issue
alert|event_spine_silent,stale_claims      ← multiple issues, one high severity
```

**Fingerprint = `status|sorted_check_names`**. Two checks compose differently from one, and different checks at the same status level produce different fingerprints.

**Alert rules:**

| Condition | Action |
|-----------|--------|
| Fingerprint changed (new or different problem) | Alert immediately |
| Same non-ok fingerprint, cooldown expired (6h default) | Repeat alert |
| Same non-ok fingerprint, cooldown not expired | Suppress |
| Fingerprint returns to `ok\|` after non-ok | Send recovery message |
| Fingerprint is `ok\|` and was already `ok\|` | Suppress (silent no-op) |

**Examples:**
- `watch|stale_claims` → `watch|event_spine_silent`: fingerprint changed → **alert immediately** (even though overall status is still `watch`)
- `watch|stale_claims` → `watch|stale_claims` (4 hours later): same fingerprint, cooldown not expired → **suppress**
- `watch|stale_claims` → `watch|stale_claims` (7 hours later): cooldown expired → **repeat alert**
- `alert|event_spine_silent` → `ok|`: recovery → **send recovery message**

## Message formats

### Alert message

```
🚨 Sentinel ALERT — Mié 27/03 14:15

2 problemas detectados

🚨 [event_spine_silent] 5 leads exist but zero events recorded
  → Verify event emission is working
⚠️ [stale_claims] 3 claims older than 24h
  → Review and release stale claims

Fingerprint: alert|event_spine_silent,stale_claims
```

### Repeat alert (same issue persists)

```
⚠️ Sentinel WATCH — Mié 27/03 20:15

1 problema detectado

⚠️ [stale_claims] 3 claims older than 24h
  → Review and release stale claims

(Repetido — mismo estado desde hace 6h)

Fingerprint: watch|stale_claims
```

### Recovery message

```
✅ Sentinel OK — Mié 27/03 14:30

Sistema recuperado. Todas las comprobaciones pasaron.
Estado anterior: watch

Fingerprint: ok|
```

## Prerequisites

### 1. n8n instance

Same requirements as other OpenClaw workflows. n8n must be running and able to reach the OpenClaw API.

**Do not expose `/internal/*` endpoints to the public internet.**

**n8n version:** Requires n8n 1.22+ (Node.js 18+ with built-in `fetch` API). If you see `fetch is not defined`, check the Node.js version inside the n8n container: `node --version`.

### 2. Telegram Bot

Same bot and chat as the other workflows. No separate bot needed.

## Configure values after import

| Value | Where | Placeholder | Example |
|-------|-------|-------------|---------|
| OpenClaw API base URL | Fetch & Evaluate code → `API_BASE` | `CONFIGURE_ME` | `http://localhost:8000` |
| OpenClaw API key | Fetch & Evaluate code → `API_KEY` | `CONFIGURE_ME` | `smoke-test-key-2026` |
| Cooldown hours | Fetch & Evaluate code → `COOLDOWN_HOURS` | `6` | `6` (default) |
| Telegram Chat ID | Send to Telegram node → Chat ID | `CONFIGURE_ME` | `692524041` |
| Telegram credential | Send to Telegram node → Credentials dropdown | (select) | `OpenClaw Telegram Bot` |

**API path note:** If n8n reaches OpenClaw through a reverse proxy that prefixes `/api`, change the fetch path in the code from `/internal/sentinel` to `/api/internal/sentinel`.

## Import and setup

1. Go to **Workflows** → **Import from File**
2. Select `sentinel-health-alert.json`
3. Verify 4 nodes appear:
   - `Poll Every 15 Minutes` — scheduleTrigger
   - `Fetch & Evaluate` — code
   - `Send to Telegram` — telegram
   - `Update State` — code
4. Open **Fetch & Evaluate** node → edit `API_BASE` and `API_KEY` at the top
5. Open **Send to Telegram** node → set Chat ID, select Telegram credential
6. Click **Execute Workflow** to test
7. Toggle workflow to **Active** when satisfied

## Testing

### Scenario A: System healthy (status = ok)

1. Ensure no stale claims, no source warnings, events are flowing
2. Execute workflow
3. Verify: Fetch & Evaluate returns 0 items (suppressed), no Telegram sent
4. Check static data: `lastFingerprint` should be `null` or `ok|`, `lastOverallStatus` should be `ok`

### Scenario B: First alert (status != ok)

1. Create a condition that triggers sentinel (e.g., create a stale claim by backdating)
2. Execute workflow
3. Verify: 1 Telegram message received with findings and recommended actions
4. Check static data: `lastFingerprint` matches the alert, `lastAlertedAt` is set

### Scenario C: Repeat suppression

1. Execute again within 6 hours, same condition
2. Verify: 0 items, no Telegram sent (cooldown suppressed)

### Scenario D: Cooldown expiry

1. Manually edit static data to set `lastAlertedAt` to 7+ hours ago
2. Execute workflow
3. Verify: Telegram message sent with "(Repetido — mismo estado desde hace Xh)"

### Scenario E: Fingerprint change

1. Change the failing condition (e.g., resolve stale claims, but trigger event_spine_silent)
2. Execute workflow
3. Verify: New alert sent immediately (fingerprint changed even if overall status is still `watch`)

### Scenario F: Recovery

1. Resolve all sentinel findings (system returns to ok)
2. Execute workflow
3. Verify: Recovery message sent ("Sistema recuperado"), `lastAlertedAt` cleared in static data

## Failure behavior

| Failure point | Behavior |
|---------------|----------|
| OpenClaw API unreachable | Code node throws, workflow fails, logged. State not updated. |
| OpenClaw returns 500 | Same as unreachable |
| System healthy (ok) | Code returns `[]`, no downstream execution |
| Alert suppressed (cooldown) | Code returns `[]`, no downstream execution |
| Telegram fails | Telegram node errors, state NOT updated (retry next poll) |
| n8n down | No execution, no alert (consider external uptime monitoring) |

**State safety:** The Update State node runs only after successful Telegram send. If Telegram fails, the fingerprint and alert timestamp are not advanced, so the next poll retries.

## What this workflow does NOT do

- Does not create, modify, or delete leads
- Does not mutate sentinel findings or OpenClaw state
- Does not compute health checks (consumes OpenClaw's sentinel output)
- Does not send messages to leads or customers
- Does not auto-remediate findings (only alerts the operator)
- Does not integrate with external monitoring systems (PagerDuty, Grafana, etc.)
- Does not replace the daily-ops-snapshot (complements it with near-real-time health monitoring)

## Relationship to OpenClaw core

**Endpoint consumed:** `GET /internal/sentinel`

- Returns `status` (ok/watch/alert), `total_findings`, and `findings[]`
- Each finding has: `check`, `surface`, `severity`, `message`, `recommended_action`
- Status is derived from highest severity finding
- Read-only, deterministic, no side effects
- Auth: `X-API-Key` header (same as other workflows)

## Relationship to other workflows

| Workflow | Schedule | Health coverage |
|----------|----------|-----------------|
| Daily Ops Snapshot | 09:00 daily | Shows system counts, no health checks |
| New Lead Notification | Every 5 min | New leads only, no health |
| Follow-up Digest | 14:00 daily | Follow-up candidates, no health |
| **Sentinel Health Alert** | **Every 15 min** | **Operational health: stale claims, source quality, event spine** |

## State management

Stored in n8n workflow static data (`$getWorkflowStaticData('global')`):

| Field | Type | Purpose |
|-------|------|---------|
| `lastFingerprint` | string | Last condition fingerprint (e.g., `watch\|stale_claims`) |
| `lastAlertedAt` | ISO string or null | When the last alert was sent (for cooldown calculation) |
| `lastOverallStatus` | string | Last overall status (for recovery message context) |

**Persistence:** Static data persists across workflow executions in n8n's database. Survives n8n restarts if data volume is correctly mounted.

**Reset:** To force an immediate alert on next poll, clear the static data via **Workflow Settings** → **Static Data** → delete or set to `{}`.

## Maintenance

- **Poll frequency change:** Edit Schedule node's `minutesInterval` value (default: 15)
- **Cooldown change:** Edit `COOLDOWN_HOURS` constant in Fetch & Evaluate code (default: 6)
- **Credential rotation:** Update `API_KEY` in code node
- **State reset:** Clear static data to force re-evaluation from scratch
- **New sentinel checks:** If OpenClaw adds new checks to `/internal/sentinel`, the workflow automatically includes them in the fingerprint (fingerprint is built from all findings, not a hardcoded list)
