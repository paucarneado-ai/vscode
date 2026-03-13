# Leads Module — Runbook Operativo

**Módulo:** leads
**Estado:** MVP operativo
**Última actualización:** 2026-03-13

---

## Endpoints

| Endpoint | Método | Qué hace |
|---|---|---|
| `/leads` | POST | Crea lead. Normaliza email/source, dedup por (email,source), scoring, 409 si duplicado. |
| `/leads` | GET | Lista leads. Filtros: `source`, `min_score`, `limit`, `offset`, `q`. Orden: id DESC. |
| `/leads/summary` | GET | Resumen: total, avg score, buckets (low/medium/high), counts por source. Mismos filtros. |
| `/leads/export.csv` | GET | CSV con columnas: id, name, email, source, score, notes. Mismos filtros. |
| `/leads/ingest` | POST | Ingesta batch. Body: `list[LeadCreate]`. Devuelve total/created/duplicates/errors. |
| `/leads/webhook/{provider}` | POST | Ingesta externa individual. Body: name, email, notes. Source = `webhook:{provider}`. |
| `/leads/webhook/{provider}/batch` | POST | Ingesta externa batch. Body: `list[{name, email, notes}]`. Source = `webhook:{provider}` (uniforme). Devuelve total/created/duplicates/errors. |
| `/leads/{id}` | GET | Detalle del lead (datos persistidos, sin campos computados). |
| `/leads/{id}/pack` | GET | Lead pack JSON: datos + rating + summary + next_action + alert. |
| `/leads/{id}/pack/html` | GET | Lead pack HTML renderizado. |
| `/leads/{id}/pack.txt` | GET | Lead pack texto plano. |
| `/leads/actionable` | GET | Lista leads accionables (next_action != discard), score DESC. Filtros: `source`, `limit`. Salida: `list[LeadOperationalSummary]`. **Nota:** con scoring placeholder actual, discriminación limitada — casi todos los leads son actionable hasta F7. |
| `/leads/actionable/worklist` | GET | Worklist operativa: agrupa actionable leads por `next_action` en orden de prioridad. Filtros: `source`, `limit`. Salida: `WorklistResponse` (generated_at, total, groups[next_action, count, leads[]]). Misma nota sobre scoring placeholder. |
| `/internal/queue` | GET | Cola operativa flat priorizada: alert first, luego por action priority y score DESC. Filtros: `source`, `limit`. Salida: `QueueResponse` (generated_at, total, urgent_count, items[]). Misma nota sobre scoring placeholder. |
| `/leads/{id}/operational` | GET | Contrato operativo flat M2M: 8 campos (lead_id, source, score, rating, next_action, alert, summary, generated_at). |
| `/leads/{id}/delivery` | GET | Delivery JSON: pack embebido + next_action/alert top-level + message dinámico. |

---

## Flujo de un lead

```
Ingesta (POST /leads, /ingest, /webhook/{provider}, /webhook/{provider}/batch)
  → Validación Pydantic (name, email, source/provider)
  → Normalización (email + source a lowercase + strip)
  → Dedup (email + source → 409 si existe)
  → Scoring (calculate_lead_score)
  → Persistencia (SQLite)
  → Respuesta (LeadCreateResult o summary batch)

Consulta operativa (GET /leads/{id}/pack o /delivery)
  → Lectura de DB
  → Cómputo: rating, summary, next_action, alert
  → Respuesta (JSON, HTML o texto)
```

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

## Si algo falla o parece incoherente

1. **Score inesperado** → revisar `services/scoring.py`. El scoring actual es un placeholder simple (base 50, +10 source test, +10 notes).
2. **Rating no cuadra con buckets** → son thresholds distintos intencionalmente (rating: 50/75, buckets: 40/60).
3. **next_action parece incorrecto** → revisar `services/actions.py`. Depende de score + notes con thresholds 60/40.
4. **Duplicado no detectado** → dedup es por (email, source) ambos normalizados. Mismo email con distinto source NO es duplicado.
5. **generated_at ≠ created_at** → correcto. generated_at es el momento de generación del delivery, no la creación del lead.
6. **delivery_status siempre "generated"** → provisional. No hay estados persistidos del lead aún.
7. **message cambia entre llamadas** → es dinámico, refleja next_action. No tratar como valor estable.
