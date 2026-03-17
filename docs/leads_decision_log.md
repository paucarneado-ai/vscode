# Leads Module — Decision Log

**Módulo:** leads
**Estado:** MVP operativo, cerrado salvo bugs, regresiones o mejoras claramente rentables
**Última actualización:** 2026-03-14

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

### D17. External ingestion adapter (`POST /leads/external`)
- **Endpoint:** `POST /leads/external` — adapter canónico para integraciones externas genéricas.
- **Contrato de entrada:** `{name, email, source, phone?, notes?, metadata?}`.
- **Contrato de salida:** `{status, lead_id, score, message}`.
- **Transformación:** phone y metadata se serializan en `notes` vía formato `@ext:` (JSON en una sola línea). Sin cambio en schema de DB.
- **Reutilización:** llama a `_create_lead_internal()` — misma dedup, scoring, persistencia.
- **Rol en jerarquía:** opción recomendada para nuevas integraciones externas que necesiten phone y/o metadata. No reemplaza ni depreca `/leads` ni `/leads/webhook/{provider}`.
- **Lo que NO es:** consolidación completa de ingesta externa. Los tres contratos coexisten.
- **Clasificación:** avance táctico limpio. No mejora estructural profunda.
- **Deuda asociada:**
  - Batch para external (no implementado, trivial con patrón existente)
  - Auth/API key (fuera de alcance)
  - Validación de phone (no implementada)
  - Source whitelist/registry (no implementado)
  - Migración de `@ext:` fields a columnas estructuradas (ver F10)
  - Consolidación de ingesta externa bajo único contrato (si se decide necesaria)
- No reabrir salvo bug, regresión o mejora claramente rentable.

### D18. Convención de `source` — documental, con enforcement parcial
- **Semántica MVP:** `source` es un identificador operativo simple del origen del lead. Se usa para dedupe `(email, source)`, persistencia, filtrado y agrupación. **No es un modelo de atribución marketing.** No debe absorber channel, campaign, vertical ni metadata de marketing — eso requiere un modelo propio (F2).
- **Convención recomendada:** `{tipo}:{identificador}` (ej. `landing:barcos-venta`, `n8n:captacion`). Recomendada globalmente.
- **Enforcement (actualizado 2026-03-14):** parcial y progresivo. Ver D19.
  - `/leads/external` — **enforced** con regex `^[a-z0-9]+:[a-z0-9][a-z0-9_-]*$`. Solo acepta formato canónico.
  - `/leads/webhook/{provider}` — **provider validado** con regex `^[a-z0-9][a-z0-9_-]*$`. Source resultante siempre canónico.
  - `/leads` y `/leads/ingest` — **sin validación**. Bare words aceptados por compatibilidad legacy.
- **~~Deuda de scoring~~** *(resuelta 2026-03-14):* la dependencia `source == "test"` en scoring fue eliminada. Scoring ya no depende del valor de source.
- **Anti-patrones documentados:** bare words ambiguos, variantes semánticas del mismo origen, sources dinámicos con IDs de ejecución, meter channel/campaign/vertical en source.
- **Triggers concretos de reapertura** para enforcement completo (cualquiera basta):
  1. 3+ callers externos reales usando sources distintos
  2. Fragmentación visible en `counts_by_source` (misma fuente real, 2+ variantes)
  3. Primer caso real de dedup falso negativo por naming inconsistente
  4. Inicio de F2 (attribution model)
  5. Introducción de source registry o whitelist
- **Clasificación:** convención documental con enforcement parcial en endpoints controlados. No es sistema de attribution ni source registry completo.
- No reabrir enforcement legacy salvo trigger concreto de los listados o mejora claramente rentable.

### D19. Source hardening — blindaje progresivo
- **Fecha:** 2026-03-14.
- **Qué se hizo:**
  1. Eliminada dependencia `source == "test"` en scoring. Score ahora solo depende de notes (base 50, +10 notes, cap 100).
  2. `/leads/external` valida source con regex canónico `^[a-z0-9]+:[a-z0-9][a-z0-9_-]*$`. Bare words rechazados con 422.
  3. `/leads/webhook/{provider}` y `/leads/webhook/{provider}/batch` validan provider con regex `^[a-z0-9][a-z0-9_-]*$` via `_validate_provider()`. Providers con caracteres especiales rechazados con 422.
  4. Endpoints legacy (`POST /leads`, `POST /leads/ingest`) no tocados — compatibilidad preservada.
- **Por qué enforcement parcial y no total:** romper callers legacy existentes (tests, scripts, posibles integraciones con bare words) sin problema operativo observable no justifica el riesgo. Los endpoints nuevos/controlados sí se blindan desde el inicio.
- **Tests añadidos:** ~14 tests de hardening cubriendo: rechazo de bare words en external, rechazo de formats inválidos, aceptación de canónicos, validación case-insensitive, compatibilidad legacy preservada, provider validation en webhooks, dedup cross-endpoint.
- **Impacto en scores existentes:** leads creados con `source == "test"` que antes obtenían score 70 (50+10+10) ahora obtendrían score 60 (50+10) si se recrearan. Leads ya persistidos no cambian (score se calcula en creación).
- **Clasificación:** endurecimiento operativo. No es feature nuevo ni cambio de contrato.
- No reabrir salvo bug o regresión.

### D20. Auditoría de módulos — correcciones preventivas
- **Fecha:** 2026-03-14.
- **Qué se hizo:**
  1. **name normalization (H1+H5):** `name` se normaliza con `strip()` en `_create_lead_internal()`. Whitespace-only rechazado con 422. Coherente con el tratamiento de `source`.
  2. **DB-level dedup (H2):** `CREATE UNIQUE INDEX uq_leads_email_source ON leads (email, source)`. `_create_lead_internal()` maneja `IntegrityError` como fallback de race condition, devolviendo la respuesta de duplicado correcta.
  3. **Scoring ignora @ext: (H4):** nueva helper `_has_user_notes()` en `scoring.py`. Solo líneas que no sean `@ext:...` cuentan como notas cualitativas. Lead con solo phone/metadata vía `/leads/external` obtiene score 50, no 60.
  4. **CSV injection sanitization (H8):** helper `_sanitize_csv_value()` prefija con `'` valores que empiecen con `=`, `+`, `-`, `@` en el export CSV.
- **Qué se documentó sin corregir:**
  - H3: `@ext:` inyectable vía `POST /leads` — no hay consumidores downstream, documentado como riesgo conocido.
  - H7: ingest batch falla entero si un item tiene payload Pydantic inválido — comportamiento estándar de FastAPI/Pydantic, documentado.
- **Tests añadidos:** 13 tests cubriendo: name whitespace rejection (4 endpoints), name strip, DB unique constraint, DB-level dedup, scoring con @ext: (3 variantes), unit test _has_user_notes, CSV sanitization (2 variantes).
- **Matiz H2 para DBs existentes:** `CREATE UNIQUE INDEX IF NOT EXISTS` se aplica automáticamente en `init_db()`. Si una DB existente ya tiene duplicados `(email, source)`, la creación del índice fallará. Esto requeriría limpieza manual previa. Para DBs nuevas y la DB de desarrollo, no hay impacto.
- **Clasificación:** endurecimiento preventivo. No es feature nuevo ni cambio de contrato visible.
- No reabrir salvo bug o regresión.

### D21. Auditoría de outputs operativos — correcciones H9, H11
- **Fecha:** 2026-03-14.
- **Qué se hizo:**
  1. **H9 — `determine_next_action` ignora @ext: (coherencia con scoring):** `actions.py` ahora usa `_has_user_notes()` de `scoring.py` en lugar de `bool(notes and notes.strip())`. Un lead con solo metadata `@ext:` y score 50 obtiene `request_more_info`, no `review_manually`. Lógica compartida, sin duplicación de heurísticas.
  2. **H11 — `ACTION_PRIORITY` movido a `actions.py`:** la constante vivía en `leads.py` (capa de routing). Movida a `actions.py` (capa de servicios) donde pertenece semánticamente. Imports actualizados en `leads.py` e `internal.py`.
- **Qué se documentó sin corregir:**
  - H10: SQL filter en `_get_actionable_leads` no distingue `@ext:` de notas reales — sin impacto con scoring actual (score siempre >= 50), latente si scoring produce scores < 40.
  - H12: worklist within-group ordering es implícito (hereda ORDER BY del query), no explícito — test existente lo cubre, fragilidad solo teórica.
  - H13: `limit` en queue/worklist se aplica pre-sort (en capa de actionable), no post-sort — sin impacto con scoring actual, latente si scoring evoluciona.
  - H14: `delivery.pack` no incluye `generated_at` pero delivery sí — diseño intencionado, no inconsistencia.
- **Tests añadidos:** 6 tests cubriendo: action @ext:-only (3 variantes unit), action e2e vía endpoint, ACTION_PRIORITY importable desde actions, ACTION_PRIORITY no definido en leads.
- **Clasificación:** corrección de coherencia (H9) y reorganización de código (H11). No es feature nuevo ni cambio de contrato visible.
- No reabrir salvo bug o regresión.

### D22. Auditoría de reporting/consulta — correcciones H15, H19
- **Fecha:** 2026-03-14.
- **Qué se hizo:**
  1. **H15 — escapar wildcards LIKE en búsqueda `q`:** `_build_where_clause` ahora escapa `%`, `_` y `\` en el patrón de búsqueda usando `ESCAPE '\'`. Afecta consistentemente a `GET /leads`, `GET /leads/summary` y `GET /leads/export.csv`.
  2. **H19 — normalizar `source` en filtro de query:** `_build_where_clause` ahora aplica `.strip().lower()` al parámetro `source` antes de usarlo en el WHERE. Coherente con la normalización de ingesta.
- **Qué se documentó sin corregir:**
  - H16: CSV export sin `created_at` — cambio de contrato (añade columna), requiere evaluación de impacto en consumidores. No implementado.
  - H17: summary sin `limit`/`offset` — diseño correcto, no problema.
  - H18: `q` no busca en `source` — `source` tiene filtro dedicado, no problema.
- **Tests añadidos:** 7 tests cubriendo: `q` con `%` literal, `q` con `_` literal, consistencia entre 3 endpoints, `source` case-insensitive, `source` con whitespace, normalización en summary y CSV.
- **Clasificación:** hardening de búsqueda y consistencia de filtros. No es feature nuevo ni cambio de contrato visible.
- No reabrir salvo bug o regresión.

---

## Supuestos provisionales

### P1. delivery_status
- Siempre `"generated"` (estático). Provisional hasta que se implementen estados del ciclo de vida del lead (context master sección 17: new/validated/qualified/delivered/etc).

### P2. Scoring engine
- Base 50, +10 si notes contiene texto de usuario real (no `@ext:` metadata). Cap 100. *(Actualizado 2026-03-14: eliminada dependencia `source == "test"` (D19), scoring ignora metadata `@ext:` (D20).)*
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
- **F12.** Batch para `/leads/external` (patrón existente, trivial).
- **F13.** Consolidación de ingesta externa bajo un único contrato (si se decide necesaria).
