# Followup CSV Export — Operator Runbook

## Endpoint

```
GET /internal/followup-automation/export.csv
```

## Query parameters

| Parameter | Required | Example | Effect |
|-----------|----------|---------|--------|
| `source`  | no       | `?source=web` | Only include leads from this source |
| `limit`   | no       | `?limit=10`   | Cap at N rows (highest-score first) |

## What you get

A downloadable CSV file (`followup-automation.csv`) containing all leads that:
- received `no_answer` as their outcome
- have not been claimed by any agent

Rows are sorted by score (highest first).

## Columns

| Column | Meaning |
|--------|---------|
| `lead_id` | Internal lead identifier |
| `to` | Recipient email address |
| `subject` | Pre-written email subject line (varies by lead tier) |
| `body` | Pre-written email body text (personalized with lead name) |
| `channel` | Always `email` (only channel supported today) |
| `priority` | Position in the list (0 = highest priority) |
| `source` | Where the lead came from |
| `score` | Lead score (0-100) |
| `rating` | Tier: `high` (75+), `medium` (50-74), `low` (<50) |

## Subject lines by tier

| Rating | Subject |
|--------|---------|
| high   | Following up — let's connect this week |
| medium | Quick follow-up |
| low    | Checking in |

## Manual spreadsheet/email workflow

1. Open the CSV in your spreadsheet tool (Excel, Google Sheets, etc.)
2. Review the rows — highest-priority leads are at the top
3. For each row:
   - Copy `to` into your email recipient field
   - Copy `subject` into the subject line
   - Copy `body` into the email body
   - Edit the message if you want to personalize further
   - Send
4. After sending, record the outcome via `POST /internal/outcomes` so the lead leaves the queue

## Known limitations

- Only `email` channel — no WhatsApp, phone, or SMS
- Subject and body are templates — they work as-is but can be edited before sending
- No "sent" tracking — the CSV is a snapshot, not a workflow. You must record outcomes separately
- No date filtering on when the `no_answer` outcome was recorded
- No pagination — use `limit` to cap large exports
- Priority is relative to the current result set and may shift between downloads

## Do not assume

- That downloading the CSV marks leads as "in progress" — it does not. The export is read-only.
- That the same lead won't appear in the next download — it will, until you record a new outcome or claim it.
- That body text is final — it is a suggestion. Edit freely before sending.
- That priority is stable — it reflects current score ranking and changes as leads are added or claimed.
