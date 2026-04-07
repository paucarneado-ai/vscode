# New Lead Notification — Staging Activation Checklist

One-time checklist to activate and verify the new-lead-notification workflow on the staging VPS.
Execute on the staging environment. Report back results per step.

**Pre-requisites verified by prior smoke test:**
- Workflow JSON is valid and importable (tested n8n 2.13.4)
- `fetch()` works in n8n Code node (Node.js 18+)
- Watermark seed, detection, pagination, dedup logic all pass (5/5 scenarios)
- Message formatting correct (notes parsing, alert prefix, score/rating/action from pack)

---

## Step 0: Transfer workflow file to VPS

The deploy script does not sync `deploy/n8n/`. Copy manually:

```bash
# From local Git Bash (repo root)
scp deploy/n8n/new-lead-notification.json root@76.13.48.227:/tmp/
```

---

## Step 1: Access n8n UI

n8n runs in Docker via EasyPanel on the VPS.

1. Open the n8n web UI in your browser (check EasyPanel for the URL/port)
2. Log in with your n8n credentials

---

## Step 2: Import workflow

1. Go to **Workflows** → **Import from File**
2. Select `/tmp/new-lead-notification.json` (or upload from your local machine)
3. Verify 4 nodes appear:
   - `Poll Every 5 Minutes` (scheduleTrigger)
   - `Detect & Prepare` (code)
   - `Send to Telegram` (telegram)
   - `Update Watermark` (code)

**Expected:** Import succeeds, all nodes visible.
**Record:** [ ] Imported OK / [ ] Issue: ___

---

## Step 3: Configure the Code node

1. Open **Detect & Prepare** node
2. At the top of the code, find:
   ```javascript
   const API_BASE = 'CONFIGURE_ME';
   const API_KEY = 'CONFIGURE_ME';
   ```
3. Replace with real values:
   - `API_BASE`: the OpenClaw API URL reachable from n8n container (e.g., `http://localhost:8000` if co-located, or `http://openclaw-api:8000` if Docker network, or `http://76.13.48.227:8080/api` if via Caddy — check which works from the n8n container)
   - `API_KEY`: your `OPENCLAW_API_KEY` value (same one used by daily-ops-snapshot)
4. Close the node

**Important:** Test the API URL first. From the n8n container, the internal endpoints must be reachable. If n8n uses the Caddy proxy path (`/api/leads`), update the code paths accordingly:
- Change `/leads?limit=` to `/api/leads?limit=`
- Change `` `/leads/${lead.id}/pack` `` to `` `/api/leads/${lead.id}/pack` ``

**Record:** [ ] API_BASE = ___ / [ ] API_KEY configured / [ ] Paths adjusted: yes/no

---

## Step 4: Configure Telegram node

1. Open **Send to Telegram** node
2. Replace `CONFIGURE_ME` in Chat ID with the real chat ID (same as daily-ops-snapshot)
3. In **Credentials** dropdown, select the existing `OpenClaw Telegram Bot` credential (same one used by daily-ops-snapshot)
4. Close the node

**Record:** [ ] Chat ID set / [ ] Telegram credential linked

---

## Step 5: Scenario A — First-run seed

1. Click **Execute Workflow**
2. Observe:
   - **Detect & Prepare** runs, returns **0 items** (empty output)
   - **Send to Telegram** does NOT execute (no input)
   - **Update Watermark** does NOT execute (no input)
   - No Telegram message arrives
3. Check static data: **Workflow Settings** (gear icon) → **Static Data** → should show `{"global":{"lastSeenId": N}}` where N is the current highest lead ID

**Expected:** Silent seed. No messages. Watermark set.
**Record:** [ ] 0 items / [ ] No Telegram / [ ] Watermark = ___

---

## Step 6: Scenario B — Repeat run, no new leads

1. Click **Execute Workflow** again (without creating any new leads)
2. Observe:
   - **Detect & Prepare** returns **0 items**
   - No downstream nodes execute
   - No Telegram message arrives

**Expected:** Duplicate suppression works.
**Record:** [ ] 0 items / [ ] No Telegram

---

## Step 7: Scenario C — One new lead

1. Create one test lead:
   ```bash
   # From VPS (or adjust URL for your access)
   curl -X POST http://127.0.0.1:8000/leads/webhook/smoke-test \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{"name":"Notif Test","email":"notif-test-1@openclaw-ops.internal","notes":"Tipo: Velero\nEslora: 12m\nMarca: Beneteau\nTelefono: +34600999888"}'
   ```
2. Click **Execute Workflow**
3. Observe:
   - **Detect & Prepare** returns **1 item**
   - **Send to Telegram** sends 1 message
   - **Update Watermark** advances lastSeenId
   - Telegram chat receives the notification

4. Verify Telegram message content:
   ```
   Nuevo lead en Sentyacht

   Nombre: Notif Test
   Email: notif-test-1@openclaw-ops.internal
   Telefono: +34600999888
   Tipo: Velero
   Eslora: 12m
   Marca: Beneteau
   Score: NN (rating)
   Accion: xxx
   Fuente: webhook:smoke-test
   ```

**Expected:** 1 message, correct content, watermark advances.
**Record:** [ ] 1 item detected / [ ] Telegram received / [ ] Content correct / [ ] Watermark = ___

---

## Step 8: Scenario D — Multiple new leads

1. Create 3 leads:
   ```bash
   curl -X POST http://127.0.0.1:8000/leads/webhook/smoke-test \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{"name":"Multi 1","email":"multi-1@openclaw-ops.internal","notes":"Tipo: Lancha\nEslora: 14m"}'

   curl -X POST http://127.0.0.1:8000/leads/webhook/smoke-test \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{"name":"Multi 2","email":"multi-2@openclaw-ops.internal","notes":"Tipo: Catamaran\nEslora: 18m"}'

   curl -X POST http://127.0.0.1:8000/leads/webhook/smoke-test \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{"name":"Multi 3","email":"multi-3@openclaw-ops.internal","notes":"Tipo: Yate\nEslora: 22m"}'
   ```
2. Click **Execute Workflow**
3. Observe:
   - **Detect & Prepare** returns **3 items**
   - **Send to Telegram** sends 3 messages
   - Telegram chat receives 3 separate notifications
   - Messages arrive in chronological order (Multi 1, Multi 2, Multi 3)

**Expected:** 3 messages, no duplicates, correct order.
**Record:** [ ] 3 items / [ ] 3 Telegram messages / [ ] Correct order / [ ] Watermark = ___

---

## Step 9: Duplicate prevention after batch

1. Click **Execute Workflow** again without creating new leads
2. Observe: 0 items, no Telegram messages

**Record:** [ ] 0 items / [ ] No Telegram

---

## Step 10: Persistence check

1. Restart n8n (via EasyPanel: stop → start, or Docker restart)
2. Wait for n8n to come back up
3. Click **Execute Workflow** (no new leads created)
4. Observe:
   - **Detect & Prepare** returns **0 items** (watermark persisted)
   - No Telegram messages

**Expected:** Watermark survives restart.
**Record:** [ ] n8n restarted / [ ] 0 items after restart / [ ] Watermark intact = ___

---

## Step 11: Activate schedule

If all scenarios pass:

1. Toggle workflow to **Active**
2. It will now poll every 5 minutes automatically
3. Verify in the next 5 minutes that no spurious messages are sent (assuming no real new leads)

**Record:** [ ] Activated / [ ] No spurious messages in first cycle

---

## Step 12: Clean up test leads (optional)

```bash
# On VPS
sqlite3 /home/openclaw/data/leads.db "DELETE FROM leads WHERE source = 'webhook:smoke-test'"
```

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| Detect & Prepare errors with "fetch is not defined" | n8n Node.js version < 18 | Check n8n container Node.js version: `node --version`. Upgrade n8n if < 1.22 |
| API returns 401/403 | Wrong API_KEY in code node | Check the value matches OPENCLAW_API_KEY |
| API connection refused | Wrong API_BASE, n8n can't reach OpenClaw | Test from n8n container: `curl http://API_BASE/health` |
| Telegram fails | Credential not linked or wrong chat ID | Re-link credential, verify chat ID |
| First run sends messages (flood) | Should not happen — code seeds silently | Check if static data was manually pre-set |
| Watermark lost after restart | n8n static data not persisting | Check n8n data volume is mounted correctly |

---

## Results summary (fill in after execution)

| Scenario | Expected | Actual | Pass? |
|----------|----------|--------|-------|
| A. Seed (first run) | 0 items, no TG, watermark set | | |
| B. Repeat (no new) | 0 items, no TG | | |
| C. One new lead | 1 item, 1 TG message | | |
| D. Multiple leads | 3 items, 3 TG messages | | |
| E. Post-batch repeat | 0 items, no TG | | |
| F. Post-restart | 0 items, watermark intact | | |
| G. Schedule active | No spurious messages | | |

**Verdict:** CLOSED / NOT CLOSED
**Notes:** ___
