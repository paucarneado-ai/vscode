# External Lead Trial — Operator Runbook

**Purpose:** Step-by-step protocol for running controlled external lead trials.
**Last updated:** 2026-03-16

---

## 1. Pre-trial setup

### Source naming

Every trial source must follow the format `trial:{identifier}`.

| Source | When to use |
|---|---|
| `trial:landing-barcos` | Leads from the boats landing page |
| `trial:meta-ads-boats` | Leads from Meta Ads for boats |
| `trial:manual-referral` | Leads entered manually from referrals |
| `trial:n8n-captacion` | Leads ingested via n8n workflow |

**Rules:**
- Always lowercase, no spaces, hyphens to separate words
- Always start with `trial:` so trial leads are instantly identifiable
- One source per real origin — do not mix origins under the same source
- Do not use bare words like `"test"` or `"facebook"`

### Recommended initial volume

- **Per source:** 5–15 leads
- **Total across sources:** 10–30 leads
- **Why:** enough to see signal in `source-intelligence`, too few to create noise

### Endpoint

All trial leads go through:

```
POST /leads/external
```

Do not use `POST /leads` or `/leads/webhook/{provider}` for trial leads.

---

## 2. Sending leads

### Minimal payload

```bash
curl -X POST http://localhost:8000/leads/external \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Maria Garcia",
    "email": "maria.garcia@example.com",
    "source": "trial:landing-barcos"
  }'
```

### Payload with phone and notes

```bash
curl -X POST http://localhost:8000/leads/external \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Carlos Lopez",
    "email": "carlos.lopez@example.com",
    "source": "trial:meta-ads-boats",
    "phone": "+34612345678",
    "notes": "Interested in 12m sailboat, Mallorca area",
    "metadata": {"campaign": "boats-spring-2026", "ad_set": "lookalike-v2"}
  }'
```

### Expected responses

**Accepted (200):**
```json
{
  "status": "accepted",
  "lead_id": 42,
  "score": 60,
  "message": "lead received"
}
```

**Duplicate (409):**
```json
{
  "status": "duplicate",
  "lead_id": 42,
  "score": 60,
  "message": "lead already exists"
}
```

**Validation error (422):** Missing fields, bad email format, or source not in `type:identifier` format.

### Scoring during trial

- Lead with notes → score 60 (medium)
- Lead without notes → score 50 (medium)
- Score does NOT depend on source name
- `@ext:` metadata alone does not count as notes

---

## 3. Daily operating checklist

Run these in order every day during the trial.

### Step 1 — Check what came in

```bash
# How many leads per trial source?
curl http://localhost:8000/leads/summary?source=trial:landing-barcos

# List recent leads from a source
curl http://localhost:8000/leads?source=trial:landing-barcos&limit=10
```

### Step 2 — Review the ops snapshot

```bash
curl http://localhost:8000/internal/ops/snapshot
```

Check: `pending_review` and `urgent` counts. If both are 0, nothing needs attention.

### Step 3 — Review actionable leads

```bash
curl http://localhost:8000/internal/daily-actions
```

This shows the top 5 leads to review, top 5 client-ready, top 5 followup candidates, and source warnings. Start with the review items.

### Step 4 — Source intelligence

```bash
# All sources
curl http://localhost:8000/internal/source-intelligence

# One trial source
curl "http://localhost:8000/internal/source-intelligence?source=trial:landing-barcos"
```

Check per source: `leads`, `avg_score`, `client_ready`, `pending_review`, `followup_candidates`, `recommendation`, `rationale`.

### Step 5 — Record outcomes

After reviewing or contacting each lead, record the real-world outcome:

```bash
# Lead was contacted and responded positively
curl -X POST http://localhost:8000/internal/outcomes \
  -H "Content-Type: application/json" \
  -d '{"lead_id": 42, "outcome": "qualified", "reason": "Wants quote for 14m Azimut"}'

# Lead was contacted but no response
curl -X POST http://localhost:8000/internal/outcomes \
  -H "Content-Type: application/json" \
  -d '{"lead_id": 43, "outcome": "no_answer"}'

# Lead is not a fit
curl -X POST http://localhost:8000/internal/outcomes \
  -H "Content-Type: application/json" \
  -d '{"lead_id": 44, "outcome": "bad_fit", "reason": "Budget too low"}'

# Lead converted
curl -X POST http://localhost:8000/internal/outcomes \
  -H "Content-Type: application/json" \
  -d '{"lead_id": 45, "outcome": "won", "reason": "Signed contract for Azimut 55"}'
```

**Allowed outcome values:** `contacted`, `qualified`, `won`, `lost`, `no_answer`, `bad_fit`

**Important:** Record outcomes as soon as they happen. Source intelligence recommendations only work when outcomes are recorded. Without outcomes, every source shows "insufficient outcome data."

### Step 6 — Followup no_answer leads

```bash
# Download followup CSV for a trial source
curl -o followup.csv "http://localhost:8000/internal/followup-automation/export.csv?source=trial:landing-barcos"
```

Then follow the manual workflow from `docs/followup_csv_runbook.md`:
1. Open CSV in spreadsheet
2. For each row: copy `to`, `subject`, `body` into email
3. Send
4. Record outcome via `POST /internal/outcomes` (step 5 above)

---

## 4. Stop / continue criteria

### When to continue a source

- `source-intelligence` shows `recommendation: "keep"` with `data_sufficient: true`
- Won + qualified rate >= 30% of outcomes
- No obvious quality problem (spam, fake emails, irrelevant leads)

### When to pause a source

- `source-intelligence` shows `recommendation: "deprioritize"` with `data_sufficient: true`
- Bad_fit + lost rate >= 50% of outcomes after 5+ outcomes
- High no_answer rate (>= 50%) after 5+ outcomes — investigate before continuing

### When to stop a source

- All leads from the source are bad_fit or lost
- Leads are clearly spam or fake
- Source produces duplicates at > 30% rate

### When data is insufficient

- `data_sufficient: false` in source-intelligence means fewer than 3 outcomes recorded
- Do not make source decisions with fewer than 3 outcomes
- Keep ingesting and recording outcomes until the recommendation becomes reliable

---

## 5. End-of-trial assessment

After all trial leads have been processed and outcomes recorded, run:

```bash
curl http://localhost:8000/internal/source-intelligence
```

For each trial source, answer:
1. How many leads came in? (`leads`)
2. How many had real outcomes? (sum of `outcomes.*`)
3. What is the recommendation? (`recommendation` + `rationale`)
4. Is the data sufficient? (`data_sufficient`)
5. How many converted? (`outcomes.won + outcomes.qualified`)
6. How many were dead weight? (`outcomes.bad_fit + outcomes.lost`)
7. How many need followup? (`followup_candidates`)

**A source is worth scaling if:**
- `recommendation` is `"keep"` with `data_sufficient: true`
- Won + qualified > bad_fit + lost
- No systematic quality issues

**A source should be dropped if:**
- `recommendation` is `"deprioritize"` with `data_sufficient: true`
- No won or qualified outcomes after 5+ leads

---

## 6. Known limitations

### What this trial CAN prove
- Whether a source produces leads that get responses (no_answer rate)
- Whether a source produces leads that convert (won/qualified rate)
- Whether leads from a source are relevant (bad_fit rate)
- Whether dedup works correctly across sources
- Whether the intake → review → outcome → followup cycle works end-to-end

### What this trial CANNOT prove
- Lead quality at scale (trial volume is too small for statistical confidence)
- Attribution value (which ad/campaign/keyword drove the lead — source is not an attribution model)
- Long-term conversion rates (some leads need weeks/months to convert)
- Scoring accuracy (scoring is a placeholder — base 50 + 10 for notes)
- Automation readiness (followup is manual CSV, not automated sending)

### Operational constraints
- No authentication on endpoints — trial must run in a controlled environment
- No "sent" tracking — operator must track what was sent externally
- No claim-on-download for CSV — same leads reappear until outcome is recorded
- Score does not differentiate lead quality — all leads score 50 or 60
- Outcomes are upsert — recording a new outcome replaces the previous one

---

## 7. Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| 422 on intake | Source not in `type:identifier` format | Use `trial:your-identifier` |
| 409 on intake | Same email + source already exists | Expected for duplicates. Check `lead_id` in response |
| Score always 50 | Lead has no notes (or only `@ext:` metadata) | Add real text in `notes` field to get 60 |
| Source not in source-intelligence | No leads exist for that source | Send at least one lead first |
| Recommendation says "insufficient data" | Fewer than 3 outcomes recorded | Record more outcomes |
| Lead reappears in followup CSV | Outcome not recorded after contact | `POST /internal/outcomes` with the real result |
| Followup CSV is empty | No leads with `no_answer` outcome, or all are claimed | Check `/internal/followup-automation` JSON for details |
