# Leads Module — Decision Log

**Módulo:** leads
**Estado:** MVP operativo, cerrado salvo bugs, regresiones o mejoras claramente rentables
**Última actualización:** 2026-03-13

---

## Decisiones congeladas

### D1. Scoring: thresholds y labels
- **Código actual:** high >= 60, medium 40–59, low < 40. Labels: `low/medium/high`.
- **Context master (sección 18):** hot 75–100, warm 45–74, cold 0–44. Labels: `hot/warm/cold`.
- **Decisión:** divergencia aceptada. No reabrir sin bloque explícito de alineación.
- **Condición de reapertura:** bloque dedicado que unifique thresholds, renombre labels y migre dependencias.

### D2. Webhook source convention
- **Convención:** `source = webhook:{provider}` vía `POST /leads/webhook/{provider}`.
- **Decisión:** suficiente para MVP. No expandir a modelo completo de atribución (source/channel/campaign/vertical) sin bloque dedicado.

### D3. next_action — heurística mínima
- **Lógica:** basada en score + notes con thresholds 60/40.
- **Catálogo activo:** `send_to_client`, `review_manually`, `request_more_info`, `enrich_first`, `discard`.
- **Catálogo diferido:** `call_now`, `reply_whatsapp` (requieren señales de canal/teléfono no disponibles).
- **Decisión:** heurística operativa para MVP, no política final de delivery.
- **Semántica de `send_to_client`:** "lead listo para entrega/priorización operativa", NO envío automático real a cliente final.

### D4. Alert — regla mínima
- `alert = score >= 60`.
- **Decisión:** regla provisional mínima. Ampliable con `premium_source`, `fast_action` u otras señales cuando existan. No reemplazar sin bloque explícito.

### D5. Delivery contract adjustment
- `generated_at` = timestamp UTC de generación del delivery (no `created_at` del lead).
- `next_action` + `alert` promovidos a top-level de `LeadDeliveryResponse`.
- `message` = campo dinámico para lectura humana/operativa. No tratar como contrato M2M.
- **Decisión:** ajuste de contrato aceptado, documentado.

### D6. Dedup por (email, source)
- Ambos normalizados a lowercase + strip.
- Duplicado → 409 Conflict, no se crea nuevo registro.
- **Decisión:** congelada para MVP.

### D7. Módulo leads cerrado
- No reabrir salvo bugs, regresiones o mejoras claramente rentables ya anotadas.

### D8. Source validation hardening
- Source vacío post-normalización → 422 en todas las vías (POST /leads, /ingest, /webhook).
- Provider vacío en webhook → 422.
- **Decisión:** endurecimiento de integridad del campo `source`, no apertura de attribution model.
- No reabrir salvo bug o regresión.

### D9. Contrato operativo (`GET /leads/{id}/operational`)
- Proyección flat M2M-friendly con 8 campos: lead_id, source, score, rating, next_action, alert, summary, generated_at.
- Fuente de verdad: `get_lead_pack()`. `operational` es proyección, no lógica paralela.
- No reemplaza pack (datos completos) ni delivery (contexto de entrega). Resuelve consumo interno/automatización.
- Conveniencia operativa de bajo coste, no obligación de crear endpoints por cada proyección futura.
- **Follow-up:** si `operational` y `delivery` convergen o uno deja de aportar valor diferencial, evaluar simplificación antes que proliferación.
- No reabrir salvo bug, regresión o mejora claramente rentable.

### D10. Leads accionables (`GET /leads/actionable`)
- Lista leads cuyo `next_action != discard`, ordenados por score DESC.
- Regla de accionabilidad MVP: `score >= 40 OR (notes not null/empty)`.
- Salida: `list[LeadOperationalSummary]` — reutiliza contrato flat M2M de D9.
- Filtros: `source` (opcional), `limit` (opcional).
- Reutiliza `get_rating()`, `determine_next_action()`, `should_alert()`, `build_summary()` — sin lógica de negocio nueva.
- **Nota operativa:** con scoring placeholder actual (base 50), la discriminación operativa es limitada — en la práctica casi todos los leads caen en actionable. El filtro será efectivo cuando se implemente scoring comercial real (F7).
- **Clasificación:** interfaz correcta y reusable para consumo interno, pero no todavía capa madura de priorización fuerte.
- **Decisión:** capa de consumo interno mínima, no plataforma de automatización.
- No reabrir salvo bug, regresión o mejora claramente rentable.

### D11. Worklist operativa (`GET /leads/actionable/worklist`)
- Agrupa leads accionables por `next_action` en orden de prioridad: `send_to_client` > `review_manually` > `request_more_info` > `enrich_first`.
- Reutiliza `_get_actionable_leads()` como fuente única — misma lógica de selección, sin duplicación.
- Contrato: `WorklistResponse` (generated_at, total, groups[WorklistGroup(next_action, count, leads[LeadOperationalSummary])]).
- Filtros: `source` (opcional), `limit` (opcional) — delegados a la capa de actionable.
- Sin reglas de negocio nuevas — solo estructuración y agrupación.
- **Nota operativa:** hereda la limitación de discriminación del scoring placeholder (D10, F7).
- **Clasificación:** consumidor interno mínimo sobre actionable, no motor de orquestación.
- **Decisión:** worklist como proyección agrupada de actionable, no sistema paralelo.
- No reabrir salvo bug, regresión o mejora claramente rentable.

### D12. Cola operativa interna (`GET /internal/queue`)
- Vista flat priorizada de leads accionables para ejecución secuencial interna.
- Reutiliza `_get_actionable_leads()` — misma fuente que worklist y actionable, sin duplicación de lógica.
- Orden: alert DESC → action priority (send_to_client > review_manually > request_more_info > enrich_first) → score DESC.
- Contrato: `QueueResponse` (generated_at, total, urgent_count, items[LeadOperationalSummary]).
- `urgent_count` = items con `alert=True`. Señal operativa rápida.
- Filtros: `source` (opcional), `limit` (opcional).
- Vive en `apps/api/routes/internal.py` — primera superficie de consumo interno separada del módulo leads.
- **Nota operativa:** hereda limitación de discriminación del scoring placeholder (D10, F7).
- **Clasificación:** cola de lectura priorizada, no sistema de despacho/workers/jobs.
- Sin semántica falsa de job/worker/dispatch. Sin estados persistidos nuevos.
- **Decisión:** consumidor interno que usa leads como motor, no extensión del módulo leads.
- **Diferenciación aceptada vs worklist:** worklist = vista agrupada por acción; queue = vista flat priorizada para ejecución secuencial; urgent_count = señal operativa rápida.
- **Vigilancia:** `_get_actionable_leads()` es reutilizada por actionable, worklist y queue. Si más superficies internas empiezan a depender de ella, evaluar extracción a `apps/api/services/`.
- **Regla de proliferación:** no crear nuevas proyecciones/salidas operativas salvo que aporten un delta funcional claro — no solo otra forma de ver lo mismo.
- No reabrir salvo bug, regresión o mejora claramente rentable.

### D13. Instruction field en contrato operativo (`LeadOperationalSummary`)
- Campo `instruction: str` añadido a `LeadOperationalSummary` como enriquecimiento aditivo del contrato existente.
- Mapping `next_action → instruction` vive en `apps/api/services/actions.py` (`get_instruction()`).
- No se creó nuevo endpoint ni contrato paralelo — se enriqueció el contrato M2M existente.
- **Cambio observable aditivo:** todos los consumidores de `LeadOperationalSummary` (actionable, worklist, queue, operational) ahora devuelven `instruction`. Consumidores JSON que ignoren campos desconocidos no se rompen, pero consumidores con validación estricta de schema verán el campo nuevo.
- **Clasificación:** mejora funcional pequeña y reusable, no nueva capa ni contrato paralelo.
- No reabrir salvo bug, regresión o mejora claramente rentable.

---

## Supuestos provisionales

### P1. delivery_status
- Siempre `"generated"` (estático). Provisional hasta que se implementen estados del ciclo de vida del lead (context master sección 17: new/validated/qualified/delivered/etc).

### P2. Scoring engine
- Base 50, +10 si source == "test", +10 si notes no vacío. Cap 100.
- Es un placeholder funcional, no un scoring comercial real. Provisional.

### P3. Rating thresholds en leadpack
- `get_rating()`: low < 50, medium 50–74, high >= 75.
- Nota: estos thresholds (50/75) son distintos de los buckets de summary (40/60) y de next_action/alert (40/60). Divergencia interna aceptada como operativa.

---

## Divergencias conocidas

### V1. Scoring: código vs context master
- **Código:** 60/40 (summary buckets, next_action, alert), 50/75 (leadpack rating).
- **Context master:** 75/45/0 con labels hot/warm/cold.
- **Estado:** aceptada, no reabrir sin bloque dedicado.

### V2. Campos canónicos
- **Context master (sección 16):** 19 campos (channel, vertical, campaign, status, classification, priority, requires_enrichment, premium_source, fast_action, next_action, etc).
- **Schema actual:** 7 columnas (id, name, email, source, notes, score, created_at).
- **Estado:** divergencia esperada. El schema actual es MVP; los campos target se implementarán por bloques cuando se necesiten.

### V3. Estados del lead
- **Context master (sección 17):** 8 estados (new, validated, needs_enrichment, qualified, duplicate_review, delivered, discarded, error).
- **Código actual:** no hay campo `status` persistido.
- **Estado:** no implementado, no requerido para MVP actual.

---

## Deuda técnica aceptada

### ~~T1. Source whitespace~~ — RESUELTA
- ~~Un `source` compuesto solo por whitespace puede persistirse como `""` tras strip.~~
- **Resolución:** `_create_lead_internal()` ahora rechaza source vacío post-strip con 422. Webhook rechaza provider vacío con 422.
- **Fecha de resolución:** 2026-03-12.
- **Nota:** endurecimiento de validación observable. No implica apertura de attribution model.

### T2. Scoring placeholder
- El scoring actual no refleja la prioridad base del context master (intención > encaje > calidad contacto > facilidad cierre > urgencia > capacidad económica).
- **Motivo:** se construyó como placeholder funcional.
- **Condición de reapertura:** bloque dedicado de scoring comercial.

### D14. Captación MVP — vertical y subcaso
- **Vertical:** barcos. **Subcaso inicial:** vendedor de barco de ocasión.
- **Por qué barcos:** acceso a operador real (empresa de barcos) para validación end-to-end.
- **Por qué vendedor primero:** lado de oferta — sin barcos no hay negocio. Feedback loop corto: lead → operador → evaluación inmediata.
- **Subcaso siguiente:** comprador de barco (segundo bloque, patrón casi idéntico).
- **Source:** `webhook:landing-barcos-venta`.
- **Decisión:** primera vertical de captación definida, no apertura de CMS ni plataforma multi-vertical.
- No reabrir salvo cambio de dirección comercial explícito.

### D15. Campos ricos en `notes` — compromiso táctico
- El formulario de vendedor captura campos ricos (tipo, eslora, marca, año, precio, ubicación) que no existen como columnas en schema de leads.
- **Decisión:** serializar como texto estructurado dentro de `notes` en lugar de tocar schema persistido.
- **Ventaja:** no requiere migración, legible por operador, parseable si se necesita.
- **Limitación:** no se puede filtrar/ordenar por campos individuales; scoring no puede usar estas señales.
- **Condición de reapertura:** cuando se necesite filtrar por campos de barco, o scoring necesite señales del formulario.
- Documentado en `docs/acquisition/acquisition_mvp.md`.

### D16. Landing como HTML estático — sin backend nuevo
- Landing `static/landing-barcos-venta.html` es HTML puro con JS inline.
- POST directo a `POST /leads/webhook/landing-barcos-venta` — reutiliza webhook existente sin cambios de código backend.
- `API_BASE` configurable via `window.OPENCLAW_API_BASE` (default `localhost:8000`).
- **Decisión:** no se necesita backend nuevo, CMS, ni framework frontend. HTML servido por cualquier medio (file, CDN, nginx).
- No reabrir salvo que se necesite tracking/analytics que requiera server-side rendering.

---

## Follow-ups explícitos

- **F1.** Alineación scoring thresholds + labels con context master (75/45/0, hot/warm/cold).
- **F2.** Modelo de atribución completo (source/channel/campaign/vertical) más allá de `webhook:{provider}`.
- **F3.** `call_now` / `reply_whatsapp` cuando existan señales de canal/teléfono.
- **F4.** Expansión de `alert` con `premium_source`, `fast_action`.
- **F5.** Estados del ciclo de vida del lead (`status` persistido).
- **F6.** `delivery_status` dinámico basado en estados reales.
- **F7.** Scoring comercial real por vertical.
- ~~**F8.** Corrección de source whitespace si causa problemas operativos.~~ — RESUELTA (D8).
- **F9.** Caso comprador de barco (`webhook:landing-barcos-compra`) como segundo bloque de captación.
- **F10.** Migración de campos ricos de `notes` a columnas/modelo estructurado cuando se necesite filtrar o scoring por señales del formulario.
- **F11.** Tracking de conversión (UTM, Meta pixel, analytics) en landings de captación.
