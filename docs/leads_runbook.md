# Leads Module — Runbook Operativo

**Módulo:** leads
**Estado:** MVP operativo
**Última actualización:** 2026-03-14

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
| `/leads/external` | POST | Ingesta externa genérica. Body: name, email, source, phone?, notes?, metadata?. Phone/metadata serializados en notes vía `@ext:`. Devuelve status/lead_id/score/message. |
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
Ingesta (POST /leads, /ingest, /webhook/{provider}, /webhook/{provider}/batch, /leads/external)
  → Validación Pydantic (name, email, source/provider)
  → Normalización (name strip, email + source a lowercase + strip)
  → Dedup (email + source → 409 si existe, con UNIQUE constraint en DB)
  → Scoring (calculate_lead_score — ignora metadata @ext:)
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

**Índice único:** `uq_leads_email_source ON leads (email, source)` — dedup atómica a nivel DB (añadido 2026-03-14).

**No hay campos persistidos para:** rating, next_action, instruction, alert, status, classification, vertical, channel, campaign. Todos los campos operativos se computan en lectura.

---

## Scoring (estado actual)

**Función:** `calculate_lead_score(source, notes) → int`
- Base: 50
- +10 si notes contiene texto de usuario real (líneas que no sean `@ext:...`)
- Cap: 100

**Notas sobre scoring:**
- Metadata técnica `@ext:` no cuenta como notas cualitativas (corregido 2026-03-14). Un lead con solo phone/metadata vía `/leads/external` obtiene score 50, no 60.
- La dependencia anterior con `source == "test"` fue eliminada en el blindaje de source (2026-03-14).
- **Esto es un placeholder funcional**, no scoring comercial real. Ver follow-up F7 en decision log.

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
| 40–59 | con notas reales | `review_manually` |
| 40–59 | sin notas reales | `request_more_info` |
| < 40 | con notas reales | `enrich_first` |
| < 40 | sin notas reales | `discard` |

**Nota:** "notas reales" = texto que no sea solo metadata `@ext:`. Un lead con solo `@ext:{...}` en notes se trata como "sin notas reales" tanto para scoring como para `determine_next_action` (corregido 2026-03-14, H9). Lógica compartida vía `_has_user_notes()` en `scoring.py`.

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

## External ingestion (`POST /leads/external`)

- Endpoint: `POST /leads/external`
- Adapter canónico para integraciones externas genéricas (formularios, landings, n8n, etc.)
- Body: `{name, email, source, phone?, notes?, metadata?}`
- Source: libre en body, normalizado a lowercase + strip. Convención recomendada: `{tipo}:{identificador}` (ej. `landing:barcos-venta`, `n8n:captacion`).
- Phone y metadata: serializados en `notes` vía formato `@ext:` (ver abajo). No tocan schema de DB.
- Respuesta: `{status: "accepted"|"duplicate", lead_id, score, message}`
- Reutiliza `_create_lead_internal()` — mismo flujo de dedup, scoring, persistencia.

### Formato `@ext:` en notes

Cuando el payload incluye `phone` y/o `metadata`, se serializan como una línea JSON al final de notes:

```
Notas originales del usuario

@ext:{"phone":"+34612345678","boat_type":"sailboat","length_m":12}
```

**Reglas:**
- Si no hay phone ni metadata, notes queda tal cual (sin marcador).
- `@ext:` va en su propia línea, precedido por `\n\n` si hay notes originales.
- Todo lo que sigue a `@ext:` en esa línea es JSON válido.
- Para parsear: `line.startswith("@ext:")` → `json.loads(line[5:])`.
- Phone va como campo `"phone"` dentro del JSON. Metadata se aplana al mismo nivel.

---

## Jerarquía de contratos de ingesta

| Endpoint | Rol | Source | Cuándo usar |
|---|---|---|---|
| `POST /leads` | Contrato general existente | Explícito en body | Creación directa interna o sistemas que controlan source |
| `POST /leads/ingest` | Bulk interno | Explícito en body (por item) | Cargas masivas con source por item |
| `POST /leads/webhook/{provider}` | Adapter provider-based | Derivado: `webhook:{provider}` | Landings y webhooks con provider fijo en URL (ej. landing-barcos-venta) |
| `POST /leads/webhook/{provider}/batch` | Batch provider-based | Derivado: `webhook:{provider}` (uniforme) | Batch de webhooks del mismo provider |
| `POST /leads/external` | **Adapter externo genérico (recomendado)** | Explícito en body, libre | Integraciones externas que necesiten phone y/o metadata |

**Notas:**
- `/leads/external` es la opción recomendada para nuevas integraciones externas genéricas.
- Los endpoints webhook existentes siguen activos y estables; no están deprecados.
- Esto NO unifica toda la ingesta externa bajo un único contrato. Es un avance táctico, no una consolidación completa.
- Todos los endpoints de ingesta convergen a `_create_lead_internal()` — misma lógica de dedup, scoring, persistencia.

---

## Semántica y convención de `source`

### Qué es `source`

`source` es un **identificador operativo simple del origen del lead**. Se usa para:
1. **Dedupe** — forma parte de la clave `(email, source)`. Mismo email con distinto source = leads distintos.
2. **Persistencia** — se guarda normalizado (lowercase, stripped).
3. **Filtrado y agrupación** — `GET /leads?source=X`, `counts_by_source` en summary, columna en CSV export.

### Qué NO es `source`

`source` **no es un modelo de atribución marketing**. No debe usarse para codificar por sí solo:
- canal de adquisición (Meta Ads, Google, orgánico, referral)
- campaña específica (campaign ID, ad set, UTM)
- vertical de negocio (boats, reforms, real estate)
- metadata de marketing (coste por lead, audiencia, segmento)

Esa atribución rica requiere un modelo propio (follow-up F2: source/channel/campaign/vertical). Meter todo eso en un solo string `source` crearía un campo sobrecargado e ingobernable. No hacerlo.

### Convención recomendada

Formato global recomendado: `{tipo}:{identificador}` — todo en minúsculas, sin espacios, guiones para separar palabras.

| Tipo | Cuándo | Ejemplos |
|---|---|---|
| `webhook:{provider}` | Generado automáticamente por `/leads/webhook/{provider}` | `webhook:facebook`, `webhook:landing-barcos-venta` |
| `landing:{nombre}` | Formularios de landing pages | `landing:barcos-venta`, `landing:contacto-web` |
| `n8n:{workflow}` | Flujos de n8n | `n8n:captacion-boats`, `n8n:enrichment` |
| `form:{nombre}` | Formularios genéricos | `form:contacto`, `form:demo-request` |
| `api:{sistema}` | Integraciones API directas | `api:crm-export`, `api:partner-sync` |

Esta convención es **recomendada, no enforced**. Se aceptan bare words existentes (ej. `"test"`, `"facebook"`) por compatibilidad MVP. No debe introducirse validación de formato ahora.

### Anti-patrones

| Evitar | Por qué | Preferir |
|---|---|---|
| `"facebook"`, `"FB"`, `"fb"` | Variantes semánticas del mismo origen, fragmentan dedup y reports | `"landing:facebook-ads"` o `"webhook:facebook"` |
| `"test"` como source de producción | Bare word sin tipo; la dependencia de scoring con `source == "test"` ya fue eliminada, pero el bare word sigue siendo un anti-patrón de naming | `"test:manual"` o `"test:integration"` |
| Espacios o mayúsculas | Se normalizan, pero mejor enviar limpio | `"landing:barcos-venta"` en vez de `"Landing: Barcos Venta"` |
| Sources dinámicos con IDs | Ej. `"n8n:run-4523"` — cada ejecución crea un source distinto, rompe dedup | `"n8n:captacion-boats"` (identificar el workflow, no la ejecución) |
| Meter channel/campaign/vertical en source | Sobrecarga el campo, impide attribution real futura | Usar `notes` o `metadata` via `/leads/external` hasta que F2 exista |

### Estado actual: debilidad aceptada, no diseño correcto

**Validación parcial implementada (2026-03-14).** El blindaje es progresivo: los endpoints nuevos/controlados validan formato; los legacy no, por compatibilidad.

Esto sigue sin ser un buen diseño final completo. La debilidad persiste en los endpoints legacy, aceptada conscientemente porque romper callers existentes no justifica el beneficio con ~2 callers reales. La ausencia de problemas operativos hoy no significa que el campo esté bien diseñado — significa que el volumen es demasiado bajo para que la debilidad se manifieste en endpoints legacy.

Estado por endpoint:
- `POST /leads` y `/leads/ingest` — **sin validación de formato**. Aceptan bare words (ej. `"test"`, `"facebook"`). Compatibilidad legacy preservada.
- `POST /leads/webhook/{provider}` — **provider validado** con regex `^[a-z0-9][a-z0-9_-]*$`. Source resultante `webhook:{provider}` siempre cumple convención canónica. Rechaza providers con caracteres especiales (422).
- `POST /leads/external` — **source validado** con regex `^[a-z0-9]+:[a-z0-9][a-z0-9_-]*$`. Solo acepta formato canónico `tipo:identificador`. Rechaza bare words (422).

### Deuda resuelta: `source == "test"` en scoring

~~`calculate_lead_score()` otorgaba +10 si `source == "test"`.~~ **Eliminado el 2026-03-14** como parte del blindaje de source. Scoring ya no depende del valor de source — solo de la presencia de notes. Esta deuda queda cerrada.

### Triggers concretos para reabrir esta decisión

Reabrir enforcement o source registry cuando ocurra **cualquiera** de estos:
1. **3 o más callers externos reales** usando `/leads/external` o `/leads` con sources distintos
2. **Fragmentación visible** en `counts_by_source`: misma fuente real aparece con 2+ variantes de source
3. **Primer caso real de dedup falso negativo** por naming inconsistente entre callers (mismo email, sources semánticamente iguales pero textualmente distintos → dos leads)
4. **Inicio de F2** (attribution model: source/channel/campaign/vertical) — en ese punto source necesita semántica estricta
5. **Introducción de source registry** o whitelist por cualquier motivo operativo

---

## Convenciones MVP vigentes

1. Dedup por (email, source) — ambos normalizados.
2. `webhook:{provider}` como convención de origen externo para webhooks.
3. `{tipo}:{identificador}` como convención recomendada para toda ingesta (ver sección anterior).
4. next_action/alert son heurísticas operativas, no política final.
5. Thresholds de código (60/40) en lugar de context master (75/45).
6. Labels low/medium/high en lugar de hot/warm/cold.
7. message en delivery es para humanos, no para máquinas.

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

1. **Score inesperado** → revisar `services/scoring.py`. El scoring actual es un placeholder simple (base 50, +10 si hay notas de usuario reales — metadata `@ext:` no cuenta).
2. **Rating no cuadra con buckets** → son thresholds distintos intencionalmente (rating: 50/75, buckets: 40/60).
3. **next_action parece incorrecto** → revisar `services/actions.py`. Depende de score + notes con thresholds 60/40.
4. **Duplicado no detectado** → dedup es por (email, source) ambos normalizados. Mismo email con distinto source NO es duplicado.
5. **generated_at ≠ created_at** → correcto. generated_at es el momento de generación del delivery, no la creación del lead.
6. **delivery_status siempre "generated"** → provisional. No hay estados persistidos del lead aún.
7. **message cambia entre llamadas** → es dinámico, refleja next_action. No tratar como valor estable.
8. **`@ext:` no aparece en notes** → solo se genera si el payload a `/leads/external` incluye `phone` o `metadata`. Sin esos campos, notes queda tal cual.
9. **metadata del caller no aparece** → si se envió vía `/leads` o `/leads/webhook/{provider}`, no hay serialización `@ext:`. Solo `/leads/external` aplica ese formato.
10. **`@ext:` aparece en notes de un lead creado vía `POST /leads`** → el endpoint legacy no impide que un caller inyecte `@ext:` manualmente en notes. Es una debilidad documentada (H3), no un bug. El sistema no parsea `@ext:` en lectura hoy — cuando lo haga, validar origen.
11. **Ingest batch falla entero por un item inválido** → si un item tiene email malformado o campos faltantes, Pydantic rechaza el request completo con 422 (no es error parcial). Solo errores dentro de `_create_lead_internal()` (ej. source vacío post-strip) se reportan como errores parciales. Comportamiento documentado (H7), no un bug.
12. **CSV export muestra valores con `'` al inicio** → sanitización contra CSV injection. Valores que empiecen con `=`, `+`, `-`, `@` se prefijan con `'` para prevenir ejecución de fórmulas en Excel.
13. **Lead con solo `@ext:` aparece como actionable con `enrich_first`** → con scoring futuro que produzca scores < 40, el filtro SQL de `_get_actionable_leads` trataría `@ext:` como notas reales y no excluiría el lead. Sin impacto hoy (score siempre >= 50). Limitación documentada (H10), no un bug con scoring actual.
14. **`limit` en queue/worklist puede excluir leads con alert** → el `limit` se aplica en la capa de actionable (ORDER BY score DESC, LIMIT N) antes de que queue reordene por alert/priority. Con scoring actual no hay impacto (alerts = score >= 60 = top por score). Limitación documentada (H13), latente si scoring evoluciona.
