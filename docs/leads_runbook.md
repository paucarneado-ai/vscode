# Leads Module — Runbook Operativo

**Módulo:** leads
**Estado:** MVP operativo
**Última actualización:** 2026-03-18

---

## Authentication

All endpoints except `/health` and `/leads/intake/web` require an API key via `X-API-Key` header.

**Public endpoint exceptions (no key required):**
- `GET /health` — infrastructure monitoring probe, must work without credentials
- `POST /leads/intake/web` — public form submission from sentyacht.es landing page, protected by Caddy surface restriction instead

> Note: CLAUDE.md states "API key requerida en todos los endpoints". These two exceptions are
> intentional MVP decisions: health needs to be probeable, and intake/web is the public-facing
> form endpoint behind Caddy's restricted surface (`POST /api/leads/intake/web` is the only
> publicly routed API path). All data-reading and operational endpoints require auth.

**Setup:**
```bash
# Add to VPS .env (required for production):
echo "OPENCLAW_API_KEY=your-secret-key-here" >> /home/openclaw/.env
echo "APP_ENV=production" >> /home/openclaw/.env
systemctl restart openclaw-api
```

**Usage:**
```bash
curl -H "X-API-Key: your-secret-key-here" http://127.0.0.1:8000/leads
```

**Behavior by environment:**
- `APP_ENV=development` or `test`, no key set: auth disabled (dev ergonomics)
- `APP_ENV=production`, no key set: **fail-closed** — all protected endpoints return 503
- `APP_ENV=production`, key set: normal auth (401 missing, 403 invalid)
- Public endpoints (`/health`, `/leads/intake/web`): always accessible regardless of auth config

---

## Endpoint Exposure Summary

| Endpoint | Caddy-public? | App auth? | Rate-limited? | Notes |
|---|---|---|---|---|
| `GET /health` | **No** (Caddy returns 403) | No | No | Only reachable via `localhost:8000` on VPS |
| `POST /leads/intake/web` | **Yes** (Caddy allows) | No | **Yes** | The ONLY publicly-routed, unauthenticated endpoint |
| All other endpoints | **No** (Caddy returns 403) | Yes (API key) | No | Reachable only via `localhost:8000` with valid `X-API-Key` |

---

## Rate Limiting

`POST /leads/intake/web` is rate-limited per client IP.

**Configuration:**
```bash
RATE_LIMIT_MAX=10      # requests per window per IP (default: 10)
RATE_LIMIT_WINDOW=60   # window in seconds (default: 60)
```
Set `RATE_LIMIT_MAX=0` to disable.

**Behavior:**
- Exceeding the limit returns `429` with `Retry-After` header (seconds until retry)
- Response body: `{"detail": "Rate limit exceeded (N requests per Ws). Try again in Xs."}`
- Each IP has an independent counter
- Counter resets after the window expires
- Auth-protected endpoints are NOT rate-limited (they require API key)

**IP extraction:**
- Uses `X-Forwarded-For` header (first entry) when behind proxy
- Falls back to direct `request.client.host`
- Trust model: uvicorn binds to `127.0.0.1`, Caddy is the only upstream, sets `X-Forwarded-For` correctly. IP spoofing via header requires bypassing Caddy, which requires VPS access.

**Limitations (MVP):**
- In-memory only: resets on process restart
- Single-worker only (we run `--workers 1` with SQLite)
- Fixed window: client can send up to 2x limit across adjacent window boundaries
- No distributed coordination
- No per-user or per-session tracking

---

## Endpoints

| Endpoint | Método | Qué hace |
|---|---|---|
| `/leads` | POST | Crea lead. Normaliza email/source, dedup por (email,source), scoring, status=new, 409 si duplicado. |
| `/leads/{id}/status` | PATCH | Actualiza estado del lead. Body: `{"status": "contacted"}`. |
| `/leads` | GET | Lista leads. Filtros: `source`, `min_score`, `limit`, `offset`, `q`. Orden: id DESC. |
| `/leads/summary` | GET | Resumen: total, avg score, buckets (low/medium/high), counts por source. Mismos filtros. |
| `/leads/export.csv` | GET | CSV con columnas: id, name, email, source, score, notes. Mismos filtros. |
| `/leads/ingest` | POST | Ingesta batch. Body: `list[LeadCreate]`. Devuelve total/created/duplicates/errors. |
| `/leads/webhook/{provider}` | POST | Ingesta externa individual. Body: `{name, email, notes?}`. Source = `webhook:{provider}`. |
| `/leads/webhook/{provider}/batch` | POST | Ingesta externa batch. Body: `[{name, email, notes?}, ...]`. Source = `webhook:{provider}`. |
| `/leads/{id}` | GET | Detalle del lead (datos persistidos, sin campos computados). |
| `/leads/{id}/pack` | GET | Lead pack JSON: datos + rating + summary + next_action + alert. |
| `/leads/{id}/pack/html` | GET | Lead pack HTML renderizado. |
| `/leads/{id}/pack.txt` | GET | Lead pack texto plano. |
| `/leads/actionable` | GET | Lista leads accionables (next_action != discard), score DESC. Filtros: `source`, `limit`. Salida: `list[LeadOperationalSummary]`. |
| `/leads/actionable/worklist` | GET | Worklist operativa: agrupa actionable leads por `next_action` en orden de prioridad. Filtros: `source`, `limit`. Salida: `WorklistResponse`. |
| `/internal/queue` | GET | Cola operativa flat priorizada: alert first, luego por action priority y score DESC. Filtros: `source`, `limit`. Salida: `QueueResponse`. |
| `/leads/{id}/operational` | GET | Contrato operativo flat M2M: 8 campos (lead_id, source, score, rating, next_action, alert, summary, generated_at). |
| `/leads/{id}/delivery` | GET | Delivery JSON: pack embebido + next_action/alert top-level + message dinámico. |

---

## Lead Scoring

Score range: 0-100. Computed deterministically at ingestion time from source + structured notes.

**Scoring rules:**

| Signal | Points | Condition |
|---|---|---|
| Base | 20 | Always |
| Source: direct web | +10 | `web:sentyacht-vender`, `web:sentyacht` |
| Source: webhook | +7 | `webhook:*` |
| Source: test | +5 | `test` |
| Has structured data | +5 | Notes field not empty |
| Phone provided | +10 | `Teléfono:` with 6+ chars |
| High-value boat type | +10 | Yate, velero, catamarán, or legacy form equivalents |
| Eslora >= 10m | +10 | Parsed from `Interés:` or `Eslora:` |
| Price indicated | +15 | `Precio orientativo:` present |
| Detail fields filled | +5 each (max +20) | Marca/modelo, Año, Puerto, Precio |
| Free-text message | +5 | `Mensaje:` with 10+ chars |

**Rating bands:**
- High: score >= 75
- Medium: score 50-74
- Low: score < 50

**Action thresholds:**
- score >= 60: `send_to_client` + alert
- score 40-59: `review_manually` (with notes) or `request_more_info` (without)
- score < 40: `enrich_first` (with notes) or `discard` (without)

**Example scenarios:**

| Lead | Score | Rating |
|---|---|---|
| Empty from unknown source | 20 | low |
| Name+email from website | 30 | low |
| + phone | 45 | low |
| + velero 12m | 65 | medium |
| + yate 18m + all details + price | 100 | high |

**Limitations:**
- Scoring is at ingestion time only; not recalculated on field updates
- Notes parsing depends on structured `Key: value` format from intake/webhook
- No ML, no external enrichment, no temporal signals

---

## Flujo de un lead

```
Ingesta (POST /leads, /ingest, /webhook/{provider}, /webhook/{provider}/batch)
  → Validación Pydantic (name, email, source/provider)
  → Normalización (email + source a lowercase + strip)
  → Dedup (email + source → 409 si existe)
  → Scoring (calculate_lead_score)
  → Persistencia (SQLite, status=new)
  → Respuesta (LeadCreateResult o summary batch)

Consulta operativa (GET /leads/{id}/pack o /delivery)
  → Lectura de DB
  → Cómputo: rating, summary, next_action, alert
  → Respuesta (JSON, HTML o texto)
```

---

## Lead Status

Operator-managed field to track lead work progress.

**Allowed statuses:**
| Status | Meaning | In queue/worklist? | Operator action |
|---|---|---|---|
| `new` | Not yet reviewed (default) | Yes (prioritized first) | Review and decide: contact, close, or discard |
| `contacted` | First contact made, awaiting response or follow-up | Yes (after `new`) | Follow up or close when resolved |
| `closed` | Deal done, lead fully handled, or resolved positively | **No** | No further action needed |
| `not_interested` | Lead declined, not viable, or not a real prospect | **No** | No further action needed |

**Ordering in queue:** Within the same score/alert level, `new` leads appear before `contacted` leads. This ensures unworked leads get attention first.

**Filter leads by status:**
```bash
curl -H "X-API-Key: $KEY" "http://127.0.0.1:8000/leads?status=new"
curl -H "X-API-Key: $KEY" "http://127.0.0.1:8000/leads?status=contacted"
```

**Update status:**
```bash
curl -X PATCH -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  http://127.0.0.1:8000/leads/{id}/status \
  -d '{"status": "contacted"}'
```

**Behavior:**
- `GET /leads` (full list) shows ALL leads regardless of status
- `GET /leads/actionable`, `/leads/actionable/worklist`, `/internal/queue` exclude `closed` and `not_interested`
- Status appears in: lead detail, operational summary, pack, queue, worklist

**Limitations (MVP):**
- No status change history (no audit trail)
- No timestamp for when status changed
- No owner/assignment
- No automated status transitions
- Status is purely operator-maintained

---

## Meta Lead Ads / n8n Integration

### Architecture
```
Meta Lead Ads → n8n (transform) → POST /leads/webhook/meta-instant → OpenClaw
```

n8n is the translation layer. OpenClaw does not integrate directly with Meta API.

### Endpoint
```
POST /leads/webhook/meta-instant
```
Requires `X-API-Key` header (same as all webhook endpoints).

### Payload contract (what n8n should send)
```json
{
  "name": "Carlos Garcia",
  "email": "carlos.garcia@example.com",
  "notes": "Teléfono: +34600111222\nTipo: Yate a motor\nEslora: 15m\nPuerto: Barcelona"
}
```

**Fields:**
- `name` (required): full name from Meta form
- `email` (required): email from Meta form
- `notes` (optional): structured text assembled by n8n from Meta fields

### Notes formatting for scoring
For maximum scoring benefit, n8n should format notes with these prefixes:
- `Teléfono: {phone}` → +10 points (intent signal)
- `Tipo: {boat_type}` → +10 if matches high-value types
- `Eslora: {length}` → +10 if >= 10m
- `Puerto: {port}` → +5 (detail signal)
- `Precio orientativo: {price}` → +15 (strongest commercial signal)
- `Marca/modelo: {brand}` → +5 (detail signal)
- `Año: {year}` → +5 (detail signal)
- `Mensaje: {free_text}` → +5 if 10+ chars

### n8n transformation template
In n8n HTTP Request node, map Meta fields to OpenClaw payload:
```
name = {{ $json.full_name }}
email = {{ $json.email }}
notes = Teléfono: {{ $json.phone_number }}
Tipo: {{ $json.boat_type }}
{{ $json.additional_details }}
```

### Duplicate handling
- Same `email` + `source` (webhook:meta-instant) = 409 duplicate
- Different `email` = new lead
- Same `email` from web form vs Meta = separate leads (different source)

### Batch ingestion
For high-volume campaigns, n8n can use the batch endpoint:
```
POST /leads/webhook/meta-instant/batch
Body: [{name, email, notes}, {name, email, notes}, ...]
```

### Querying Meta leads
```bash
curl -H "X-API-Key: $KEY" "http://127.0.0.1:8000/leads?source=webhook:meta-instant"
curl -H "X-API-Key: $KEY" "http://127.0.0.1:8000/leads/summary?source=webhook:meta-instant"
```

### Limitations (MVP)
- No direct Meta API integration (n8n does the bridging)
- No sync back to Meta (no conversion API yet)
- No campaign/ad-level attribution in lead data (add as notes if needed)
- Scoring uses same rules as web leads — no Meta-specific scoring adjustments

---

## Schema persistido

Tabla `leads`: id, name, email, source, notes, score, created_at.

**No hay campos persistidos para:** rating, next_action, instruction, alert, status, classification, vertical, channel, campaign. Todos los campos operativos se computan en lectura.

---

## Scoring (estado actual)

**Función:** `calculate_lead_score(source, notes) → int`
- Base: 50
- +10 si source == "test"
- +10 si notes no vacío
- Cap: 100

**Esto es un placeholder funcional**, no scoring comercial real. Ver follow-up F7 en decision log.

---

## Rating (leadpack)

**Función:** `get_rating(score) → str`
- low: score < 50
- medium: 50 ≤ score < 75
- high: score ≥ 75

**Nota:** estos thresholds (50/75) son distintos de los buckets de summary (40/60).

---

## Summary buckets

En `GET /leads/summary`:
- low: score < 40
- medium: 40 ≤ score < 60
- high: score ≥ 60

---

## next_action (computado)

**Función:** `determine_next_action(score, notes) → str`

| Score | Notes | next_action |
|---|---|---|
| ≥ 60 | — | `send_to_client` |
| 40–59 | con notas | `review_manually` |
| 40–59 | sin notas | `request_more_info` |
| < 40 | con notas | `enrich_first` |
| < 40 | sin notas | `discard` |

`send_to_client` = "listo para priorización operativa", NO envío automático a cliente final.

---

## Instruction (computado)

**Función:** `get_instruction(next_action) → str`

| next_action | instruction |
|---|---|
| `send_to_client` | Send lead to client for prioritization |
| `review_manually` | Review lead manually |
| `request_more_info` | Request more information from lead |
| `enrich_first` | Enrich lead data before further action |
| `discard` | Discard lead — insufficient data |

Derivado 1:1 de `next_action`. Presente en `LeadOperationalSummary` (actionable, worklist, queue, operational).

---

## Alert (computado)

`should_alert(score) → bool` = `score >= 60`

Regla mínima provisional. Ampliable con premium_source, fast_action cuando existan.

---

## Delivery

- `generated_at`: timestamp UTC del momento de generación, NO fecha de creación del lead.
- `next_action` + `alert`: promovidos a top-level (también dentro de `pack`).
- `message`: dinámico, orientado a lectura humana. NO usar como contrato M2M.
- `delivery_status`: siempre `"generated"` (provisional).
- `pack`: embebido completo, idéntico al de `GET /leads/{id}/pack`.

---

## Webhook ingestion

- Endpoint: `POST /leads/webhook/{provider}`
- Source resultante: `webhook:{provider}` (provider normalizado a lowercase + strip)
- Body: `{name, email, notes}` (sin source — viene del path)
- Respuesta: `{status: "accepted"|"duplicate", lead_id: N}`
- Reutiliza `_create_lead_internal()` — mismo flujo de dedup, scoring, persistencia.

---

## Convenciones MVP vigentes

1. Dedup por (email, source) — ambos normalizados.
2. `webhook:{provider}` como convención de origen externo.
3. next_action/alert son heurísticas operativas, no política final.
4. Thresholds de código (60/40) en lugar de context master (75/45).
5. Labels low/medium/high en lugar de hot/warm/cold.
6. message en delivery es para humanos, no para máquinas.

---

## Qué NO tocar sin justificación fuerte

- Schema persistido (tabla leads)
- Scoring de negocio (calculate_lead_score)
- Reglas de dedup
- Thresholds actuales (sin bloque de alineación dedicado)
- Contratos de endpoints existentes

---

## Divergencias código vs context master

| Aspecto | Context master | Código actual |
|---|---|---|
| Thresholds scoring | 75/45/0 | 60/40 (buckets, actions), 50/75 (rating) |
| Labels clasificación | hot/warm/cold | low/medium/high |
| Campos del lead | 19 canónicos | 7 persistidos |
| Estados del lead | 8 estados | no implementado |
| Dedup fuerte | email O teléfono | email + source |

Todas aceptadas como divergencias MVP. Ver decision log para condiciones de reapertura.

---

## Backups

SQLite backup via cron (recommended setup on VPS):
```bash
# Add to root crontab:
sudo crontab -e
# Add this line (runs daily at 3am):
0 3 * * * /home/openclaw/app/deploy/ops/backup-sqlite.sh >> /home/openclaw/backups/backup.log 2>&1
```

Backups are stored in `/home/openclaw/backups/` with timestamps.
Retention: keeps 30 most recent, deletes older automatically.
Verify: `bash /home/openclaw/app/deploy/ops/check-staging.sh` (reports backup count + freshness).

**Manual backup anytime:**
```bash
bash /home/openclaw/app/deploy/ops/backup-sqlite.sh
```

**Restore from backup:**
```bash
bash /home/openclaw/app/deploy/ops/restore-sqlite.sh
# Interactive: lists backups, prompts for selection
# Or direct: bash restore-sqlite.sh leads_20260318_030000.db
```
The restore script: stops API, creates pre-restore snapshot, validates backup integrity, restores, restarts API.
To rollback a bad restore: run restore again with the `pre_restore_*.db` snapshot file.

---

## Incident Recovery

**API is down:**
```bash
systemctl status openclaw-api
journalctl -u openclaw-api --no-pager -n 30
systemctl restart openclaw-api
```

**Site not loading (Caddy):**
```bash
systemctl status caddy
systemctl restart caddy
```

**Database corrupted:**
```bash
# 1. Check integrity
sqlite3 /home/openclaw/data/leads.db "PRAGMA integrity_check"
# 2. If failed, restore from latest backup
bash /home/openclaw/app/deploy/ops/restore-sqlite.sh
```

**Leads not being created:**
```bash
# Run intake smoke test
bash /home/openclaw/app/deploy/ops/smoke-intake.sh
# If FAIL: check API logs
journalctl -u openclaw-api --no-pager -n 20
```

**Full operational check:**
```bash
bash /home/openclaw/app/deploy/ops/check-staging.sh
```

---

## Sentry Error Tracking

**Backend** (Python): configured in `apps/api/main.py` via `SENTRY_DSN` env var.
**Frontend** (JS): configured in `static/site/config.js` + `static/site/shared.js`.

**Verify backend Sentry is receiving events:**
```bash
ssh root@VPS '/home/openclaw/venv/bin/python -c "
import sentry_sdk, os
sentry_sdk.init(dsn=os.environ.get(\"SENTRY_DSN\", \"\"))
sentry_sdk.capture_message(\"test backend sentry\")
print(\"Sent\")
"'
```
Check Sentry dashboard (project python-fastapi) for the test message.

**Verify frontend Sentry:**
Open any page on sentyacht.es, open browser console, run:
```js
Sentry.captureMessage("test frontend sentry");
```
Check Sentry dashboard (project browser-javascript).

**If Sentry is not receiving events:**
1. Check `SENTRY_DSN` is set in `/home/openclaw/.env`
2. Check uvicorn restarted after setting the variable
3. Check `config.js` has the frontend DSN (non-empty `SENTRY_DSN` field)

---

## Si algo falla o parece incoherente

1. **Score inesperado** → revisar `services/scoring.py`. Scoring determinístico basado en source + campos en notes.
2. **Rating no cuadra con action** → ambos usan los mismos thresholds: low (<40), medium (40-59), high (>=60).
3. **next_action parece incorrecto** → revisar `services/actions.py`. Depende de score + notes con thresholds 60/40.
4. **Duplicado no detectado** → dedup es por (email, source) ambos normalizados. Mismo email con distinto source NO es duplicado.
5. **generated_at != created_at** → correcto. generated_at es el momento de generación del delivery, no la creación del lead.
6. **delivery_status siempre "generated"** → provisional. No hay estados persistidos del lead aún.
7. **message cambia entre llamadas** → es dinámico, refleja next_action. No tratar como valor estable.
