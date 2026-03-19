# Project Drift Report

Generated: 2026-03-19T04:33:34.110053+00:00

Reconciles 4 layers: audit doc, master plan, previous scan, and repo filesystem.

## Changes since last scan (2026-03-19T04:33:33.635124+00:00)

No changes detected since last scan.
## Reconciliation: needs validation

- **Catálogo público SentYacht** (audit: DONE): files in audit but not in repo: config.js, shared.js
- **n8n / Meta Ads Integration** (audit: PARTIAL): files in audit but not in repo: docs/briefs/meta_n8n.md
- **integrate_galleries.py** (audit: DEPRECATED): files in audit but not in repo: scripts/integrate_galleries.py, scripts/integrate_galleries.py
- **gallery-reorder.html** (audit: DEPRECATED): files in audit but not in repo: tools/gallery-reorder.html, tools/gallery-reorder.html
- **Scraping scripts** (audit: DONE): files in audit but not in repo: scripts/scrape_galleries.py, scrape_all_galleries.py, scrape_test_one.py
- **Operational Layer** (plan phase: MVP): in master plan but not in audit — Cola priorizada, worklist, lead pack, delivery
- **Automation Interface** (plan phase: MVP): in master plan but not in audit — Endpoints para n8n/Zapier (queue polling, webhook intake)
- **Admin de barcos** (plan phase: MVP): in master plan but not in audit — Panel interno para gestionar barcos, galerías, texto
- **Landing de compra** (plan phase: Posterior): in master plan but not in audit — Página para compradores potenciales
- **Corporate site** (plan phase: Posterior): in master plan but not in audit — Web institucional de SentYacht
- **n8n workflows** (plan phase: MVP): in master plan but not in audit — Meta Lead Ads → webhook → lead engine
- **CRM sync** (plan phase: Posterior): in master plan but not in audit — Exportación a herramientas externas

## Filesystem drift (37 items: 0 high, 1 medium, 36 low)

### Medium

- **HTML page not in audit: /vender/**: File static/site/vender/index.html exists but not mentioned in audit

### Low

- **API route not in audit: GET /demo/intake**: Defined in apps/api/routes/demo.py
- **API route not in audit: GET /health/detail**: Defined in apps/api/routes/health.py
- **API route not in audit: POST /internal/dispatch/claim**: Defined in apps/api/routes/internal.py
- **API route not in audit: DELETE /internal/dispatch/claim/{lead_id}**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/dispatch**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/handoffs**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/handoffs/export.csv**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/review**: Defined in apps/api/routes/internal.py
- **API route not in audit: POST /internal/review/{lead_id}/claim**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/ops/snapshot**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/client-ready**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/worklist**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/source-performance**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/source-actions**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/events**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/sentinel**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/audit**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/redundancy**: Defined in apps/api/routes/internal.py
- **API route not in audit: POST /internal/scope-critic**: Defined in apps/api/routes/internal.py
- **API route not in audit: POST /internal/proof-verifier**: Defined in apps/api/routes/internal.py
- **API route not in audit: POST /internal/drift-detector**: Defined in apps/api/routes/internal.py
- **API route not in audit: POST /internal/outcomes**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/outcomes/summary**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/outcomes/by-source**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/followup-queue**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/source-outcome-actions**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/daily-actions**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/followup-handoffs**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/followup-automation**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/followup-automation/export.csv**: Defined in apps/api/routes/internal.py
- **API route not in audit: GET /internal/source-intelligence**: Defined in apps/api/routes/internal.py
- **API route not in audit: POST /leads/external**: Defined in apps/api/routes/leads.py
- **API route not in audit: GET /leads/sources**: Defined in apps/api/routes/leads.py
- **Python module not in audit: apps/api/events.py**: 38 lines, 1 functions
- **Python module not in audit: apps/api/automations/followup_bridge.py**: 121 lines, 2 functions
- **Python module not in audit: apps/api/routes/demo.py**: 92 lines, 1 functions

