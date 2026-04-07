# n8n Daily Ops Snapshot — Runbook

## What this workflow does

Sends a Telegram message every workday morning with an actionable summary of the operator's pending work in OpenClaw. One API call to `/internal/daily-actions`, one to `/internal/ops/snapshot`, formatted into a structured message.

**Workflow file:** `deploy/n8n/daily-ops-snapshot.json`

## Message sections

| Section | Source | What it answers |
|---------|--------|-----------------|
| Header | `/internal/ops/snapshot` | System totals: leads, actionable, urgent |
| HOY PRIMERO (max 5) | Derived from daily-actions data | "What should I do first?" — urgent reviews, client-ready sends, stale follow-ups |
| REVISAR | `top_review` | Leads needing manual review |
| LISTOS PARA ENVIAR | `top_client_ready` | Leads ready for client contact |
| FOLLOW-UP | `top_followup` | Leads with outcome=no_answer, with contact attempt enrichment |
| ALERTAS DE FUENTE | `source_warnings` | Sources with problematic outcome patterns |

**HOY PRIMERO priority order:**
1. Urgent review items (`alert=true`)
2. Client-ready leads (highest value action)
3. Follow-up leads not recently contacted (`recently_contacted=false`)

No business logic is computed in n8n. All prioritization, scoring, and classification comes from OpenClaw.

## Prerequisites

### 1. n8n instance

n8n must be running and able to reach the OpenClaw API.

**Preferred deployment:** co-located on the same VPS or internal network as OpenClaw.

```
# Example: n8n on same VPS as OpenClaw
# OpenClaw API reachable at http://localhost:8000
# No public exposure of internal endpoints needed
```

**Alternative:** n8n on a separate host with network access to the OpenClaw API port. In this case, ensure the connection is private (VPN, internal network, or firewall-restricted). **Do not expose `/internal/*` endpoints to the public internet.**

### 2. Telegram Bot

1. Open Telegram, find `@BotFather`
2. Send `/newbot`, follow prompts
3. Save the bot token (format: `123456789:ABCdef...`)
4. Create a group or use a private chat with the bot
5. Get the chat ID:
   - Add the bot to the group
   - Send a message in the group
   - Visit `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Find `"chat":{"id":-1001234567890}` in the response

### 3. Configure values in the workflow nodes

The workflow uses **hardcoded placeholder values** that you replace directly in the n8n UI after import. n8n v2+ restricts `$env` access by default, so values are configured in-node, not via environment variables.

| Value | Where to set | Default placeholder | Example real value |
|-------|-------------|---------------------|-------------------|
| OpenClaw API URL | "Fetch Ops Snapshot" node → URL field | `http://localhost:8000/internal/ops/snapshot` | `http://localhost:8000/internal/ops/snapshot` |
| OpenClaw API URL | "Fetch Daily Actions" node → URL field | `http://localhost:8000/internal/daily-actions` | `http://localhost:8000/internal/daily-actions` |
| API Key | Header Auth credential → Value field | (none — you create this) | Your `OPENCLAW_API_KEY` value |
| Telegram Chat ID | "Send to Telegram" node → Chat ID field | `CONFIGURE_ME` | `692524041` or your group ID |

**Auth setup — Header Auth credential:**
1. In n8n, go to Credentials → Add Credential → "Header Auth"
2. Set **Name** (header name): `X-API-Key`
3. Set **Value**: your OpenClaw API key (e.g., `smoke-test-key-2026`)
4. Save, then select this credential in both HTTP Request nodes

**Auth behavior:**
- In **dev/test** (`APP_ENV=development` or `APP_ENV=test`): OpenClaw bypasses API key validation if `OPENCLAW_API_KEY` is not set. The workflow will work without a key.
- In **staging/production**: `OPENCLAW_API_KEY` must be set in both OpenClaw and n8n. Missing or invalid keys return 401/403.
- The Header Auth credential sends the `X-API-Key` header on every request. This is the correct behavior — it works in dev (bypassed) and prod (validated).

### 4. Telegram credentials in n8n

After importing the workflow, configure the Telegram API credentials:
1. Go to **Credentials** in n8n
2. Create new **Telegram API** credential
3. Paste the bot token from BotFather
4. Name it `OpenClaw Telegram Bot`
5. In the "Send to Telegram" node, select this credential

## Import and setup

### Step 1: Import workflow

1. Open n8n web UI
2. Go to **Workflows** → **Import from File**
3. Select `deploy/n8n/daily-ops-snapshot.json`
4. The workflow appears with all nodes pre-configured

### Step 2: Configure schedule

Default: **09:00 Europe/Madrid, every day**.

To change:
- **Time:** Edit the "Schedule" trigger node → change `triggerAtHour` / `triggerAtMinute`
- **Days:** Edit the trigger node settings to include/exclude specific days
- **Timezone:** Go to **Workflow Settings** (gear icon) → change `timezone` field

The timezone is set at the workflow level in n8n settings, not per-node.

### Step 3: Configure Telegram credentials

See "Telegram credentials in n8n" above. The `Send to Telegram` node will show a warning until credentials are linked.

### Step 4: Test manually

1. Click **Execute Workflow** in the n8n editor
2. Check each node's output:
   - `Fetch Ops Snapshot` should return JSON with `total_leads`, `actionable`, etc.
   - `Fetch Daily Actions` should return JSON with `summary`, `top_review`, etc.
   - `Format Telegram Message` should produce a `text` field with the formatted message
   - `Send to Telegram` should show success and the message should appear in the configured chat

### Step 5: Activate

Toggle the workflow to **Active**. It will run on the configured schedule.

## Failure behavior

| Failure point | What happens |
|---------------|-------------|
| OpenClaw API unreachable | HTTP Request node returns error. n8n logs the execution as failed. No Telegram message sent. |
| OpenClaw API returns error (500, etc.) | Same as unreachable — error logged, no message sent. |
| Ops Snapshot fails but Daily Actions succeeds | Message is sent without the system header line (the formatter handles missing snapshot data gracefully). |
| Telegram API fails | n8n logs the execution as failed. The data was fetched but not delivered. |
| n8n itself is down | No execution happens. No alert. Consider external uptime monitoring for n8n if critical. |

**Error executions are saved** (`saveDataErrorExecution: all` in workflow settings). Check n8n's execution log to diagnose failures.

**No retry loop.** If the message fails, it fails for that day. The next day's execution runs independently. For MVP, this is acceptable — the operator can always query the API directly.

## Network diagram

```
┌──────────────────────────────────┐
│           n8n instance           │
│                                  │
│  Schedule ──► Fetch ──► Format   │
│               (2 API calls)      │
│                    │             │
│                    ▼             │
│              Send Telegram       │
└────────────────┬─────────────────┘
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

**Preferred path:** n8n calls OpenClaw via `localhost` or internal network address. Internal endpoints (`/internal/*`) should not be exposed publicly. Telegram delivery goes outbound via HTTPS — this is the only external network call.

## What this workflow does NOT do

- Does not create, modify, or delete any leads
- Does not mutate outcomes or contact attempts
- Does not compute scoring or priority (consumes OpenClaw's)
- Does not send messages to leads or customers
- Does not integrate with Meta, WhatsApp, or any external lead source
- Does not replace the API — it's a read-only consumer

## Relationship to OpenClaw core

This workflow consumes two existing read-only endpoints:

| Endpoint | Auth | Purpose in workflow |
|----------|------|---------------------|
| `GET /internal/ops/snapshot` | none (internal) | System-level counts for the header |
| `GET /internal/daily-actions` | none (internal) | All operational categories + enrichment |

No OpenClaw code was created or modified for this workflow. The API surfaces existed before this block.

## Maintenance

- **Workflow updates:** Edit in n8n UI or re-import the JSON file. The JSON in `deploy/n8n/` is the canonical source.
- **API contract changes:** If `daily-actions` or `ops/snapshot` response shapes change, the formatter code node may need updating. Both endpoints are documented in `docs/operational_contracts.md`.
- **Telegram bot rotation:** Update the credential in n8n. No workflow changes needed.
- **Schedule changes:** Edit the trigger node or workflow timezone in n8n settings.
