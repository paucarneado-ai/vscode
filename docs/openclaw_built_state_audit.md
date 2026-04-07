# OpenClaw — Built State Audit

Fecha: 2026-03-19
Commit: c54706a (dev)

## Clasificación

| Tag | Significado |
|---|---|
| DONE | Construido, testeado, usable en producción |
| MOSTLY_DONE | Funcional pero con gaps menores documentados |
| PARTIAL | Existe código pero no está completo o integrado |
| SCAFFOLD | Estructura creada, contenido placeholder |
| PLANNED | Documentado/diseñado pero sin código |
| DEPRECATED | Código que ya no se usa activamente |

---

## 1. Lead Engine — DONE

**Archivos**: apps/api/services/intake.py, scoring.py, actions.py, leadpack.py, operational.py
**Tests**: ~130 tests en test_api.py + test_intake_normalization.py + test_lead_status.py
**Líneas**: ~615 de servicios

Incluye:
- Ingesta con normalización (email, source strip+lower)
- Deduplicación por email+source (nivel app, no DB constraint)
- Scoring determinista 0-100 con 10+ señales comerciales
- Status tracking (new → contacted → closed/not_interested)
- Lead Pack: rating + summary + next_action + instructions
- Operational summary: phone extraction, priority_reason, alert flag
- Actionable filtering: score >= 40 OR has notes, excluye closed/not_interested

**Por qué DONE**: toda la funcionalidad prevista para MVP está implementada y cubierta por tests. Los gaps conocidos (race condition en dedup, LIKE sin escape) están documentados como deuda técnica aceptada.

## 2. API Routes — DONE

**Archivos**: apps/api/main.py, apps/api/routes/leads.py, health.py, internal.py, admin.py
**Endpoints**: 30 endpoints operativos
**Tests**: cubiertos por test_api.py y test_auth.py

| Grupo | Endpoints | Estado |
|---|---|---|
| Health | GET /health | DONE |
| Lead CRUD | POST /leads, GET /leads, GET /leads/{id} | DONE |
| Batch | POST /leads/ingest | DONE |
| Public intake | POST /leads/intake/web | DONE |
| Webhooks | POST /leads/webhook/{provider} | DONE |
| Webhook batch | POST /leads/webhook/{provider}/batch | DONE |
| Status | PATCH /leads/{id}/status | DONE |
| Pack | GET /leads/{lead_id}/pack | DONE |
| Pack HTML | GET /leads/{lead_id}/pack/html | DONE |
| Pack text | GET /leads/{lead_id}/pack.txt | DONE |
| Operational | GET /leads/{lead_id}/operational | DONE |
| Delivery | GET /leads/{lead_id}/delivery | DONE |
| Queue | GET /internal/queue | DONE |
| Worklist | GET /leads/actionable/worklist | DONE |
| Summary | GET /leads/summary | DONE |
| Export | GET /leads/export.csv | DONE |
| Admin boats | GET/PUT/POST /internal/admin/boats/* | DONE |
| Admin build | POST /internal/admin/build | DONE |

**Por qué DONE**: todos los endpoints del plan MVP están implementados con contratos definidos, validación, y tests.

## 3. Auth & Rate Limiting — DONE

**Archivos**: apps/api/auth.py, ratelimit.py
**Tests**: test_auth.py (12 tests), test_ratelimit.py (10 tests)

- API key via X-API-Key header
- Fail-closed en producción, fail-open en dev sin key
- Rate limiting per-IP con fixed window
- Retry-After header
- X-Forwarded-For extraction para proxy chains

**Por qué DONE**: funcionalidad completa para single-worker MVP. La limitación de in-memory (reset on restart) es aceptada.

## 4. Database — DONE (con limitaciones aceptadas)

**Archivos**: apps/api/db.py (46 líneas)
**Schema**: 1 tabla (leads: id, name, email, source, notes, score, status, created_at)

- SQLite con connection pooling
- Migration automática (add status column)
- reset_db() para tests

**Por qué DONE**: suficiente para MVP. La deuda técnica (sin UNIQUE constraint para dedup, single-writer) está documentada y es aceptable con SQLite + 1 worker.

## 5. Catálogo público SentYacht — DONE

**Archivos**: static/site/ (boats.js, styles.css, config.js, shared.js, HTML pages)
**Páginas**: 2 home (`/es/`, `/en/`) + 2 catálogo (`/es/yates-en-venta/`, `/en/yachts-for-sale/`) + 24 detail pages (12 ES + 12 EN)

- Web estática bilingüe (ES/EN)
- 12 barcos con fichas completas (specs, precio, descripción, galería)
- Catálogo con filtros (tipo, marca, eslora, año, búsqueda)
- Formulario de contacto (Formspree placeholder)
- GLightbox para galerías
- Meta Pixel tracking
- JSON-LD schema.org
- Responsive (Tailwind CDN)
- Visibility filtering (visible/draft)

**Gap menor**: Formspree form ID sigue como `YOUR_FORM_ID` placeholder en los formularios de fichas de barco.

**Páginas adicionales en el sitio** (no parte del catálogo de barcos pero sí del site):
- Root `/` → redirect a `/es/`
- Landing vendedor: `/es/vender-mi-barco/` (ver sección 10)
- Legal ES: aviso-legal, politica-de-privacidad, politica-de-cookies
- Legal EN: legal-notice, privacy-policy, cookie-policy

**Por qué DONE**: el catálogo es funcional, desplegable, y sirve su propósito de captación.

## 6. Admin Panel de barcos — DONE

**Archivos**: tools/admin.html, apps/api/routes/admin.py, apps/api/services/admin.py
**Endpoints**: 10 endpoints admin

- Login con API key (sessionStorage)
- Listado de barcos con hero, precio, estado (publicado/borrador)
- Edición de texto: todos los campos del barco (nombre, specs, descripción ES/EN, precio, badges)
- Edición de galería: drag & drop (SortableJS)
- Guardar borrador / Guardar y publicar
- Publicar / Ocultar (visibility toggle)
- Crear barco nuevo (scaffold completo)
- Preview ES/EN en nueva pestaña

**Por qué DONE**: flujo completo de operador sin editar archivos manualmente.

## 7. Build Pipeline — DONE

**Archivos**: scripts/build_site.py (803 líneas), static/site/data/boats/*.json (12 archivos)
**Genera**: boats.js + 24 HTML pages

- JSON-per-boat como fuente de verdad
- Genera boats.js con helper functions
- Genera páginas de detalle ES/EN completas (nav, gallery, specs, form, similar boats, footer, JSON-LD, Meta Pixel)
- Validation-first (aborta si hay errores)
- <1 segundo de build

**Por qué DONE**: pipeline funcional que elimina la edición manual de HTML.

## 8. Deploy & Ops — MOSTLY_DONE

**Archivos**: deploy/ (7 archivos + 6 scripts ops)

- deploy-staging.sh: sincronización completa con VPS
- setup-vps.sh: setup inicial
- Caddyfile: reverse proxy con superficie pública restringida
- systemd service: uvicorn single worker
- Ops: backup, restore, verify, check, smoke

**Gap**: no hay CI/CD automatizado (deploy es manual via script). No hay monitoring/alerting (Sentry está integrado pero no confirmado que recibe eventos). No hay cron de backup configurado en el VPS.

**Por qué MOSTLY_DONE**: todo el tooling existe y funciona, pero la operación continua (cron, monitoring) no está activada.

## 9. n8n / Meta Ads Integration — PARTIAL

**Archivos**: docs/integration/n8n_interface.md, docs/briefs/meta_n8n.md

- Webhook endpoints implementados y testeados (POST /leads/webhook/meta-instant)
- Interface documentada (polling queue, pack detail)
- n8n corre en Docker en el VPS (EasyPanel)

**Gap real**: no hay workflow n8n configurado y probado con leads reales de Meta Ads. El endpoint existe, la documentación existe, pero el cable Meta → n8n → OpenClaw no está enchufado y validado end-to-end.

**Por qué PARTIAL**: la API está lista, la documentación está lista, pero la integración no se ha activado ni probado con datos reales.

## 10. Landing de captación vendedores — DONE

**Archivo**: `static/site/es/vender-mi-barco/index.html` (383 líneas)
**URL pública**: https://sentyacht.es/es/vender-mi-barco/
**Endpoint**: POST `/api/leads/intake/web` (público, rate-limited)
**Source**: `web:sentyacht-vender` (HIGH_QUALITY, +10 scoring)
**En producción**: Sí

Incluye:
- Hero con imagen de fondo y copy premium
- 3 value props (experiencia, posicionamiento, trato directo)
- Formulario: nombre, email, teléfono, interés (select), mensaje
- POST a `/api/leads/intake/web` con `origen: web:sentyacht-vender`
- Manejo de éxito (200 y 409 duplicate), error con fallback a teléfono
- Fallback a mailto si API no disponible
- Checkbox de privacidad
- Spinner en botón de envío
- CTA final con teléfono, WhatsApp, email
- Meta Pixel tracking
- Nav completa con menú móvil
- Footer completo con legal
- Responsive mobile-first

**Documentación asociada**: docs/acquisition/ (3 archivos: brief, circuito, MVP definition)
**Tests e2e**: test_smoke.py incluye tests de la landing (carga, formulario, duplicado)
**Deploy**: deploy-staging.sh y check-staging.sh verifican la landing

**Gaps menores**: no hay versión EN, no hay honeypot anti-bot, campo teléfono no es obligatorio (el brief lo pedía obligatorio).

**Por qué DONE**: página completa en repo y en producción, con formulario funcional que ingesta leads al motor.

## 11. Pathway Discovery — DONE (herramienta interna)

**Archivos**: apps/pathway_discovery/ (10 archivos + 18 tests)
**Líneas**: ~5.000

- Análisis AST de interacciones entre módulos
- Detección de candidatos a pathways (5 tipos)
- Scoring de confianza
- CLI interactivo para revisión
- Registro de decisiones

**Por qué DONE**: es una herramienta de desarrollo, no un feature de producto. Está completa para su propósito.

## 12. Schemas & Contracts — DONE

**Archivos**: apps/api/schemas.py (109 líneas)

- LeadCreate, LeadResponse, LeadCreateResult
- WebhookLeadPayload, WebIntakePayload
- LeadOperationalSummary, LeadPackResponse, LeadDeliveryResponse
- WorklistGroup, WorklistResponse, QueueResponse
- LeadStatusUpdate, VALID_LEAD_STATUSES

**Por qué DONE**: todos los contratos del MVP definidos con Pydantic validation.

## 13. Documentación — MOSTLY_DONE

**Archivos**: docs/ (11 archivos, ~2.100 líneas)

- context_master.md: referencia canónica del proyecto
- leads_runbook.md: guía operativa completa
- gallery_runbook.md: gestión de barcos y galerías
- decision logs: historial de decisiones
- integration docs: n8n interface
- acquisition docs: vertical de vendedores

**Gap**: hay divergencia documentada entre context_master y código real (thresholds de scoring). Faltan docs EN (todo está en ES o mixto).

**Por qué MOSTLY_DONE**: cobertura amplia, pero necesita sincronización con estado actual.

## 14. integrate_galleries.py — DEPRECATED

**Archivo**: scripts/integrate_galleries.py (28 líneas)

Wrapper que delega a build_site.py. Mantenido por compatibilidad.

## 15. gallery-reorder.html — DEPRECATED (de facto)

**Archivo**: tools/gallery-reorder.html

Herramienta standalone de reorden de galería. Suplantada por el admin panel que hace lo mismo integrado. Sigue funcionando pero ya no es el flujo principal.

## 16. Scraping scripts — DONE (utilidad)

**Archivos**: scripts/scrape_galleries.py, scrape_all_galleries.py, scrape_test_one.py

Scrapers de imágenes de barcos desde cosasdebarcos.com. Funcionan pero son one-time utilities.

## 17. Notificaciones — PLANNED

No existe código. Ni WhatsApp, ni email, ni push. La idea aparece en docs como fase siguiente.

## 18. Dashboard / Métricas — PLANNED

No existe código. GET /leads/summary da datos agregados pero no hay UI de dashboard.

## 19. Market Data Layer — PLANNED

Mencionado en CLAUDE.md como fase futura. Sin código, sin diseño detallado.

## 20. Formspree — SCAFFOLD

Todos los formularios de contacto usan `action="https://formspree.io/f/YOUR_FORM_ID"`. El placeholder no está configurado con un ID real.

---

## Resumen por clasificación

| Tag | Módulos |
|---|---|
| **DONE** | Lead Engine, API Routes, Auth & Rate Limiting, Database, Catálogo público, Admin Panel, Build Pipeline, Landing vendedores, Pathway Discovery, Schemas, Scraping scripts |
| **MOSTLY_DONE** | Deploy & Ops, Documentación |
| **PARTIAL** | n8n / Meta Ads integration |
| **SCAFFOLD** | Formspree form ID (fichas de barco) |
| **PLANNED** | Notificaciones, Dashboard, Market Data, Landing EN vendedores |
| **DEPRECATED** | integrate_galleries.py, gallery-reorder.html (de facto) |

---

## Gap Analysis + Next Best Block

### 1. Diferencias clave entre plan objetivo y estado actual

| Plan | Estado real | Gap |
|---|---|---|
| Leads de Meta Ads entrando automáticamente | Endpoint existe, n8n documentado, pero NO activado | **Cable sin enchufar** |
| Landing de captación de vendedores | DONE — `/es/vender-mi-barco/` en repo y producción | Cerrado (falta versión EN) |
| Formulario web funcional | Placeholder YOUR_FORM_ID en todas las fichas | **No operativo** |
| Notificaciones al operador | Solo idea | **No diseñado** |
| Dashboard de métricas | Solo /leads/summary como API | **No hay UI** |
| Backup automático | Script existe, cron no instalado | **No activado** |

### 2. Zonas con trabajo suficiente (no tocar más por ahora)

- **Lead engine**: scoring, actions, intake, operational — completo y testeado. No necesita más trabajo hasta que haya leads reales para validar thresholds.
- **Admin de barcos**: texto + galería + visibilidad + build — ciclo completo. Solo mejorar si hay feedback de uso real.
- **Catálogo público**: 12 barcos con fichas completas bilingües. Funcional para su propósito actual.
- **Deploy tooling**: scripts de deploy, ops, backup/restore — todo existe. Falta activar, no construir más.
- **Documentación de arquitectura**: context_master, decision logs, runbooks — suficiente para contexto. No necesita más docs hasta el siguiente bloque grande.

### 3. Siguientes 5 bloques ordenados por ROI

| # | Bloque | Esfuerzo | Impacto | ROI |
|---|---|---|---|---|
| **1** | **Activar n8n + Meta Ads end-to-end** | Bajo (config, no código) | Alto (primer lead automatizado real) | **Máximo** |
| **2** | **Configurar Formspree real** | Mínimo (cambiar un string) | Alto (formularios web operativos) | **Muy alto** |
| **3** | **Instalar cron de backup + verificar Sentry** | Bajo (config) | Medio (resiliencia operativa) | **Alto** |
| **4** | **Landing de vendedores** | Medio (HTML + webhook) | Alto (nueva fuente de captación) | **Alto** |
| **5** | **Notificaciones WhatsApp/email al operador** | Medio (integración externa) | Alto (reduce tiempo de respuesta) | **Medio-alto** |

### 4. Recomendación principal: Activar n8n + Meta Ads

**El siguiente bloque debería ser activar la integración n8n → Meta Lead Ads end-to-end.**

### 5. Por qué este bloque gana

- **No requiere código nuevo**: el endpoint POST /leads/webhook/meta-instant ya existe y está testeado. La documentación de n8n está escrita. Es pura configuración.
- **Es el primer lead real automatizado**: hasta ahora el sistema procesa leads de test. El primer lead de Meta Ads que entre y se cualifique automáticamente valida todo el pipeline.
- **Desbloquea feedback real**: sin leads reales no puedes validar si el scoring tiene sentido, si los thresholds son correctos, si el operador entiende la cola.
- **ROI inmediato**: Meta Ads ya puede estar corriendo campañas. El cable n8n → OpenClaw es lo único que falta para que los leads aterricen.
- **Riesgo bajo**: si falla, solo falla la config de n8n. No hay riesgo de romper nada construido.

El segundo quick win es configurar Formspree (literalmente cambiar un placeholder por un ID real) para que los formularios de contacto de las fichas de barcos funcionen.

### 6. Qué NO hacer todavía

- **No construir dashboard**: sin leads reales no hay datos que mostrar. Primero activar la fuente.
- **No refactorizar scoring**: los thresholds son heurísticos. Necesitan validación con datos reales antes de ajustar.
- **No añadir segunda vertical**: SentYacht aún no ha procesado su primer lead automatizado. Prematuro.
- **No migrar de SQLite**: para el volumen actual (decenas-centenares de leads) es suficiente. Migrar ahora es overhead sin beneficio.
- **No construir market data layer**: sin leads reales ni volumen, no hay contexto para precios de referencia.
- **No mejorar el admin panel**: funciona. Esperar feedback de uso real antes de iterar.
