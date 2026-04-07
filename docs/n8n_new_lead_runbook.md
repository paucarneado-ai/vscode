# n8n New Lead Notification — Runbook

## What this workflow does

Polls OpenClaw every 5 minutes for new leads and sends a Telegram message for each one. Uses paginated fetching with watermark-based deduplication to guarantee no lead is skipped and no duplicate notifications are sent under normal operation.

**Workflow file:** `deploy/n8n/new-lead-notification.json`

## Message format

Each new lead produces one Telegram message:

```
🚨 URGENTE                      ← only if OpenClaw flags alert=true

Nuevo lead en Sentyacht

Nombre: Didac Senties
Email: didacsenties93@gmail.com
Telefono: +34622205223
Tipo: Lancha a motor
Eslora: 18m
Marca: Azimut 62
Score: 60 (medium)
Accion: send_to_client
Fuente: webhook:landing-barcos-venta
```

Fields extracted from the lead pack. Phone, boat type, length, and brand are parsed from the `notes` field (supports both plain-text `Key: value` and `@ext:` JSON formats). Missing fields show `N/A`.

No business logic is computed in n8n. Urgency (`alert`), scoring, rating, and next action all come from OpenClaw.

## Prerequisites

### 1. n8n instance

Same requirements as the daily-ops-snapshot workflow. n8n must be running and able to reach the OpenClaw API.

**Preferred deployment:** co-located on the same VPS or internal network as OpenClaw.

**Do not expose `/leads/*` or `/internal/*` endpoints to the public internet.**

**n8n version:** Requires n8n 1.22+ (Node.js 18+ with built-in `fetch` API). The Detect & Prepare code node uses `fetch()` for paginated HTTP requests.

### 2. Telegram Bot

Same bot and chat as the daily-ops-snapshot. No separate bot needed.

If you haven't set up a bot yet, see the daily-ops-snapshot runbook (`docs/n8n_daily_ops_runbook.md` → "Telegram Bot" section).

### 3. Configure values after import

The workflow contains **placeholder values only** — no real secrets in the repo artifact. You configure everything in the n8n UI after import.

| Value | Where to set | Placeholder | Example real value |
|-------|-------------|-------------|-------------------|
| OpenClaw API base URL | "Detect & Prepare" code node → `API_BASE` constant | `CONFIGURE_ME` | `http://localhost:8000` |
| OpenClaw API key | "Detect & Prepare" code node → `API_KEY` constant | `CONFIGURE_ME` | Your `OPENCLAW_API_KEY` value, or `''` for dev |
| Telegram Chat ID | "Send to Telegram" node → Chat ID field | `CONFIGURE_ME` | `692524041` or your group ID |
| Telegram credential | "Send to Telegram" node → Credentials dropdown | (none linked) | Select `OpenClaw Telegram Bot` |

**Auth behavior:**
- In **dev/test** (`APP_ENV=development`): set `API_KEY = ''` (empty string) in the code node. OpenClaw bypasses API key validation when `OPENCLAW_API_KEY` is not set.
- In **staging/production**: set `API_KEY` to match the `OPENCLAW_API_KEY` configured in OpenClaw. Missing or invalid keys return 401/403.

### 4. Telegram credentials in n8n

Reuse the same Telegram API credential from the daily-ops-snapshot workflow. Select it in the "Send to Telegram" node. If you haven't created one yet, see the daily-ops-snapshot runbook.

## Import and setup

### Step 1: Import workflow

1. Open n8n web UI
2. Go to **Workflows** → **Import from File**
3. Select `deploy/n8n/new-lead-notification.json`
4. The workflow appears with 4 nodes

### Step 2: Configure the code node

1. Open the "Detect & Prepare" node
2. At the top of the code, find these two lines:
   ```javascript
   const API_BASE = 'CONFIGURE_ME'; // e.g. 'http://localhost:8000'
   const API_KEY = 'CONFIGURE_ME';  // OPENCLAW_API_KEY value, or '' for dev
   ```
3. Replace `CONFIGURE_ME` with your real values
4. Close the node

### Step 3: Configure Telegram

1. Open the "Send to Telegram" node
2. Replace `CONFIGURE_ME` in the Chat ID field with your Telegram chat ID
3. In the Credentials dropdown, select your `OpenClaw Telegram Bot` credential
4. Close the node

### Step 4: Configure schedule (optional)

Default: **every 5 minutes**. To change:
- Open the "Poll Every 5 Minutes" node → change `minutesInterval`
- Timezone: **Workflow Settings** (gear icon) → change `timezone` field (default: `Europe/Madrid`)

### Step 5: Test manually — first run (seed)

1. Click **Execute Workflow** in the n8n editor
2. Expected behavior:
   - "Detect & Prepare" runs, fetches the most recent lead, **stores its ID as the watermark**, and returns no items
   - "Send to Telegram" and "Update Watermark" do **not** execute (no items to process)
   - No Telegram message is sent
3. This is correct. The first run seeds the watermark so that only future leads trigger notifications.

**If OpenClaw has zero leads:** The watermark stays unset. The workflow retries seeding on the next poll. No error.

### Step 6: Test — new lead detection

1. Create a test lead in OpenClaw:
   ```bash
   curl -X POST http://localhost:8000/leads/webhook/test \
     -H "Content-Type: application/json" \
     -d '{"name":"Test Notif","email":"test-notif@openclaw-ops.internal","notes":"Tipo: Velero\nEslora: 12m\nMarca: Beneteau"}'
   ```
2. Click **Execute Workflow** again
3. Expected behavior:
   - "Detect & Prepare" finds the new lead (ID > watermark), fetches its pack, formats the message
   - "Send to Telegram" sends one message to your chat
   - "Update Watermark" advances the watermark to the new lead's ID
4. Verify the Telegram message arrived with correct fields

### Step 7: Test — duplicate prevention

1. Click **Execute Workflow** again without creating new leads
2. Expected behavior:
   - "Detect & Prepare" finds no new leads (all IDs <= watermark), returns no items
   - No Telegram message sent
3. This confirms deduplication is working

### Step 8: Activate

Toggle the workflow to **Active**. It will poll every 5 minutes.

## First-run behavior

| System state | First-run behavior |
|---|---|
| Leads exist in OpenClaw | Seeds watermark to highest lead ID. No notifications sent. |
| Zero leads in OpenClaw | Watermark stays unset. No error. Retries on next poll. |
| Watermark already set (re-import) | Normal operation — only leads with ID > watermark trigger notifications. |

## Failure behavior

| Failure point | What happens | Watermark updated? |
|---|---|---|
| OpenClaw API unreachable | Code node throws. Workflow fails. | No — next poll retries. |
| API returns error (500, 401) | Code node throws. Workflow fails. | No — next poll retries. |
| No new leads detected | Code node returns empty. Workflow stops naturally. | No (nothing to update). |
| Pack fetch fails for a lead | Code node throws. Workflow fails. | No — next poll retries all. |
| Telegram fails | Telegram node errors. Workflow fails. | No — next poll retries all. |
| All succeed | All nodes complete. | Yes — advances to max processed ID. |

**Error executions are saved** (`saveDataErrorExecution: all`). Check n8n's execution log to diagnose failures.

**At-least-once delivery:** If Telegram succeeds for some messages but fails on a later one, the watermark is NOT updated. The next poll re-sends all new leads since the last watermark, including ones already delivered. The operator may see a duplicate rather than miss a lead. Accepted trade-off for MVP.

## Watermark mechanics

The workflow tracks `lastSeenId` in n8n's workflow static data (`$getWorkflowStaticData('global')`). This persists across executions.

- **Advances only** after successful Telegram delivery (node 4)
- **Never advances** if any upstream node fails
- **Computed from** `Math.max(lead_id)` of all successfully processed items
- **Visible in** n8n's static data viewer (Workflow Settings → Static Data)

**Recovery:** If the watermark is lost (e.g., n8n reinstall), the workflow re-seeds on the next run. No leads are lost — but no retroactive notifications are sent for leads that existed before the re-seed.

## N+1 pack fetch — accepted MVP trade-off

The workflow fetches `/leads/{id}/pack` once per new lead detected. For a burst of 10 new leads, that's 10 sequential API calls. This is a conscious MVP choice:

- **Why:** The pack endpoint provides all enrichment (score, rating, next_action, alert, summary) in one call. Reusing it avoids duplicating business logic.
- **Limitation:** For high-volume scenarios (50+ leads per poll), a batch pack endpoint would be more efficient. Not needed at current scale.
- **Pagination is safe:** The detection phase fetches leads in pages of 50, stopping as soon as it reaches the watermark. The pack fetches only run for confirmed new leads.

## Network diagram

```
┌──────────────────────────────────────┐
│           n8n instance               │
│                                      │
│  Schedule ──► Detect & Prepare       │
│               (paginated fetch,      │
│                watermark check,      │
│                pack fetch per lead)  │
│                    │                 │
│                    ▼                 │
│              Send Telegram           │
│                    │                 │
│                    ▼                 │
│            Update Watermark          │
└────────────────┬─────────────────────┘
                 │
    ┌────────────┼────────────────┐
    │ internal   │                │
    │ network    ▼                │
    │   ┌─────────────────┐      │
    │   │  OpenClaw API   │      │
    │   │  :8000          │      │
    │   └─────────────────┘      │
    └─────────────────────────────┘
                 │
                 │  Telegram Bot API
                 ▼  (outbound HTTPS)
          ┌──────────────┐
          │   Telegram   │
          │   operator   │
          │   chat/group │
          └──────────────┘
```

## What this workflow does NOT do

- Does not create, modify, or delete any leads
- Does not mutate outcomes, contact attempts, or claims
- Does not compute scoring, priority, or alert status (consumes OpenClaw's)
- Does not send messages to leads or customers
- Does not integrate with Meta, WhatsApp, email, or any external channel
- Does not replace the API — it's a read-only consumer
- Does not maintain a secondary source of truth — watermark is operational state only

## Relationship to OpenClaw core

This workflow consumes two existing read-only endpoints:

| Endpoint | Auth | Purpose in workflow |
|----------|------|---------------------|
| `GET /leads?limit=N&offset=N` | X-API-Key | Paginated detection of new leads (ORDER BY id DESC) |
| `GET /leads/{id}/pack` | X-API-Key | Full enriched lead data for the notification message |

No OpenClaw code was created or modified for this workflow. Both endpoints existed before this block.

## Relationship to daily-ops-snapshot

| Aspect | Daily Ops Snapshot | New Lead Notification |
|--------|-------------------|----------------------|
| **Trigger** | Cron 09:00 daily | Cron every 5 min |
| **Purpose** | Daily summary of all pending work | Per-lead alert on arrival |
| **Endpoints** | `/internal/ops/snapshot`, `/internal/daily-actions` | `/leads?limit=N`, `/leads/{id}/pack` |
| **Messages** | One per day | One per new lead |
| **Dedup** | None needed (daily schedule) | Watermark-based (lastSeenId) |
| **Telegram** | Same bot and chat | Same bot and chat |

Both workflows are read-only consumers. They can run concurrently without interference.

## Maintenance

- **Workflow updates:** Edit in n8n UI or re-import the JSON file. The JSON in `deploy/n8n/` is the canonical source.
- **API contract changes:** If `/leads` list or `/leads/{id}/pack` response shapes change, the code node may need updating. Both endpoints are documented in `docs/operational_contracts.md`.
- **Telegram bot rotation:** Update the credential in n8n. No workflow changes needed.
- **Schedule changes:** Edit the trigger node interval in n8n settings.
- **Watermark reset:** Clear static data in Workflow Settings → Static Data. Next run re-seeds.
