# n8n Follow-up Action Digest — Runbook

## What this workflow does

Sends an afternoon Telegram digest of actionable follow-up leads. Runs daily at 14:00 (Europe/Madrid), skips weekends. Shows only leads that have **not** been contacted recently (72-hour window), grouped by priority tier, with copy-paste suggested messages.

**Workflow file:** `deploy/n8n/followup-digest.json`

## Message format

```
📋 Follow-up pendientes — Mié 27 Mar

3 leads pendientes de follow-up

🔴 ALTA (2)
  • #12 Alice — score 80 — sin contactar
    → "Hi Alice, I wanted to personally follow up..."
  • #8 Bob — score 75 — 1 intento, hace 5d
    → "Hi Bob, I wanted to personally follow up..."

🟡 MEDIA (1)
  • #15 Carlos — score 60 — 2 intentos, hace 3d
    → "Hi Carlos, following up on my previous message..."

Generado: 2026-03-27T14:00:00Z
```

Per lead: ID, name, score, contact history, and suggested message (copy-paste ready). Grouped by rating tier (🔴 high, 🟡 medium, 🟢 low). Maximum 5 leads shown with full detail; overflow shows `+ N más`. Empty tiers are omitted. If no actionable follow-ups exist, no message is sent.

No business logic is computed in n8n. Score, rating, instruction, suggested message, and `recently_contacted` status all come from OpenClaw.

## Prerequisites

### 1. n8n instance

Same requirements as the daily-ops-snapshot and new-lead-notification workflows. n8n must be running and able to reach the OpenClaw API.

**Preferred deployment:** co-located on the same VPS or internal network as OpenClaw.

**Do not expose `/internal/*` endpoints to the public internet.**

**n8n version:** Requires n8n 1.22+ (Node.js 18+ with built-in `fetch` API). The Fetch & Format code node uses `fetch()` for HTTP requests. If you see `fetch is not defined`, check the Node.js version inside the n8n container: `node --version`. This is the same runtime constraint as the new-lead-notification workflow.

### 2. Telegram Bot

Same bot and chat as the other workflows. No separate bot needed.

If you haven't set up a bot yet, see the daily-ops-snapshot runbook (`docs/n8n_daily_ops_runbook.md` → "Telegram Bot" section).

## Configure values after import

After importing the workflow JSON, update these placeholders:

| Value | Where | Placeholder | Example |
|-------|-------|-------------|---------|
| OpenClaw API base URL | Fetch & Format code → `API_BASE` | `CONFIGURE_ME` | `http://localhost:8000` |
| OpenClaw API key | Fetch & Format code → `API_KEY` | `CONFIGURE_ME` | `smoke-test-key-2026` |
| Telegram Chat ID | Send to Telegram node → Chat ID | `CONFIGURE_ME` | `692524041` |
| Telegram credential | Send to Telegram node → Credentials dropdown | (select) | `OpenClaw Telegram Bot` |

**API path note:** If n8n reaches OpenClaw through a reverse proxy (e.g., Caddy) that prefixes `/api`, change the fetch path in the code from `/internal/followup-automation` to `/api/internal/followup-automation`.

## Import and setup

1. Go to **Workflows** → **Import from File**
2. Select `followup-digest.json`
3. Verify 3 nodes appear:
   - `Schedule (Daily 14:00)` — scheduleTrigger
   - `Fetch & Format` — code
   - `Send to Telegram` — telegram
4. Open **Fetch & Format** node → edit `API_BASE` and `API_KEY` at the top
5. Open **Send to Telegram** node → set Chat ID, select Telegram credential
6. Click **Execute Workflow** to test
7. Toggle workflow to **Active** when satisfied

## Testing

### Scenario A: With actionable follow-ups

1. Ensure at least one lead has `outcome = 'no_answer'` and has NOT been contacted in the last 72 hours
2. Click **Execute Workflow**
3. Verify: Fetch & Format returns 1 item, Telegram receives message with correct tier grouping and suggested message

### Scenario B: No actionable follow-ups

1. Either no leads have `outcome = 'no_answer'`, or all have been contacted recently
2. Click **Execute Workflow**
3. Verify: Fetch & Format returns 0 items, no Telegram message sent

### Scenario C: Weekend guard

1. If testing on a weekend (or temporarily set your system clock):
2. Click **Execute Workflow**
3. Verify: Fetch & Format returns 0 items immediately (weekend guard), no Telegram message

### Scenario D: Overflow (>5 leads)

1. Ensure more than 5 leads have `outcome = 'no_answer'` and are not recently contacted
2. Click **Execute Workflow**
3. Verify: Message shows 5 leads with full detail, then `+ N más` for the remainder

## Failure behavior

| Failure point | Behavior |
|---------------|----------|
| OpenClaw API unreachable | Code node throws, workflow fails, logged as error execution |
| OpenClaw returns 500 | Same as unreachable |
| Zero actionable items | Code returns `[]`, workflow stops, no Telegram sent (not an error) |
| Weekend execution | Code returns `[]`, workflow stops, no Telegram sent (not an error) |
| Telegram API fails | Telegram node errors, workflow fails, logged |
| n8n itself down | No execution, no alert (consider external uptime monitoring) |

**No retry loop.** If the message fails, it fails for that day. Next day's execution runs independently. The workflow is stateless — no watermark to corrupt, no state to lose.

## What this workflow does NOT do

- Does not create, modify, or delete leads
- Does not send messages to leads or customers (internal operator notification only)
- Does not record contact attempts
- Does not mutate outcomes or any OpenClaw state
- Does not compute scoring, rating, or priority (consumes OpenClaw's)
- Does not integrate with Meta, WhatsApp, or external lead sources
- Does not replace the daily-ops-snapshot (complements it — morning overview + afternoon follow-up focus)

## Relationship to OpenClaw core

**Endpoint consumed:** `GET /internal/followup-automation`

- Returns all leads with `outcome = 'no_answer'`, excluding claimed
- Ordered by `score DESC, lead_id ASC`
- Each item includes enrichment: `last_contacted_at`, `contact_attempts_count`, `recently_contacted`
- `recently_contacted` uses a 72-hour window on outbound contact attempts
- This workflow filters to `recently_contacted === false` in the Code node (not in the API)
- Auth: `X-API-Key` header (same as other workflows)

## Relationship to other workflows

| Workflow | Schedule | Focus | Content overlap |
|----------|----------|-------|-----------------|
| Daily Ops Snapshot | 09:00 weekdays | Everything: review, client-ready, follow-up, source warnings | Shows top 5 follow-ups as one section, no suggested messages |
| New Lead Notification | Every 5 min | New leads only | None — different trigger, different data |
| **Follow-up Digest** | **14:00 daily** | **Follow-ups only** | **Afternoon complement to morning snapshot. Adds: suggested messages, recently_contacted filter, tier grouping** |

## Weekend handling

The schedule trigger uses `triggerAtHour: 14` format (same as daily-ops-snapshot), which fires every day including weekends. Weekday restriction is enforced by a guard in the Code node:

```javascript
const day = now.getDay();
if (day === 0 || day === 6) return [];
```

This is a deliberate design choice: the `triggerAtHour` format is the only schedule pattern verified in the deployed n8n runtime. The `cronExpression` alternative exists in n8n docs but has not been tested in this environment. The Code node guard is testable and produces the same result.

`new Date()` in the Code node uses the n8n process timezone, which is set to `Europe/Madrid` at the workflow level.

## Maintenance

- **Schedule change:** Edit the Schedule node's `triggerAtHour` / `triggerAtMinute` values
- **MAX_DETAILED change:** Edit the `MAX_DETAILED` constant in the Code node (default: 5)
- **Credential rotation:** Update API key in the Code node's `API_KEY` constant
- **Telegram changes:** Same credential management as other workflows
- **Endpoint changes:** If `/internal/followup-automation` response shape changes, the Code node's field access paths must be updated
