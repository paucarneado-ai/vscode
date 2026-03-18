# Brief: Meta Ads + n8n Integration

## Purpose
Ingest leads from Meta Lead Ads / Instant Forms into OpenClaw via n8n.

## Current scope
- Endpoint: POST /leads/webhook/meta-instant (uses existing webhook infrastructure)
- n8n workflow: Meta Lead Ads Trigger → Map Fields → HTTP Request → Error check
- Payload: {name, email, notes} where notes has structured `Key: value` lines
- Source: `webhook:meta-instant`
- Auth: X-API-Key header (same as all webhook endpoints)

## Key files
- `apps/api/services/intake.py` — normalize_webhook_payload()
- `apps/api/routes/leads.py` — webhook_ingest(), webhook_ingest_batch()
- `docs/leads_runbook.md` — Meta/n8n integration section

## n8n connectivity
- n8n runs in Docker on same VPS (EasyPanel)
- URL: http://172.17.0.1:8000/leads/webhook/meta-instant
- NOT through public domain (Caddy blocks /api/* except intake/web)

## Scoring
- Source `webhook:meta-instant` gets +7 (MEDIUM_QUALITY_SOURCES via prefix match)
- Notes scoring works if n8n formats with correct prefixes (Teléfono:, Tipo:, etc.)
- Prefix matching: `source_lower.startswith(s)` handles A/B suffixes

## Frozen decisions
- n8n is the translation layer, not OpenClaw
- OpenClaw does not integrate directly with Meta API
- No Meta Conversions API (CAPI) yet
- No campaign/ad-level attribution in lead data yet

## Do not touch
- Webhook endpoint contract (name, email, notes)
- Source naming convention (webhook:{provider})
- Scoring prefix matching logic

## Accepted debt
- boat_details from Meta is free text dumped as Mensaje: (no structured parsing)
- No Meta app production review yet (test mode only)
- No alerting on n8n workflow failures

## Likely next block
- Meta Conversions API (feed conversion events back to Meta for optimization)
- Add structured fields to Meta form for better scoring

## See also
- Adding a new provider? Pattern is the same: normalize_webhook_payload() in intake.py
- Changing scoring for Meta leads? Also read `docs/briefs/leads_core.md`
- Debugging n8n connectivity? See runbook Meta/n8n section for correct URL by deployment
