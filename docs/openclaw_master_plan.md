# OpenClaw — Master Plan

## Visión

OpenClaw es una plataforma de captación y cualificación de leads para negocios de alto valor unitario (yates, inmobiliario, vehículos premium). El core es un motor de leads reutilizable. La primera vertical es SentYacht (brokerage de yates en Barcelona).

El objetivo no es un CRM genérico. Es un sistema operativo de captación que:
1. Recibe leads de múltiples fuentes (web, Meta Ads, webhooks)
2. Los cualifica automáticamente (scoring determinista)
3. Los presenta al operador priorizados y con instrucciones claras
4. Gestiona el catálogo público (web estática bilingüe)

## Estructura por módulos

### CORE REUSABLE (agnóstico de vertical)

| Módulo | Función | Fase |
|---|---|---|
| **Lead Engine** | Ingesta, normalización, dedup, scoring, status tracking | MVP |
| **Operational Layer** | Cola priorizada, worklist, lead pack, delivery | MVP |
| **Auth & Rate Limiting** | API key, per-IP rate limiting, fail-closed production | MVP |
| **Automation Interface** | Endpoints para n8n/Zapier (queue polling, webhook intake) | MVP |
| **Pathway Discovery** | Auditoría estructural del código, detección de deuda técnica | Infraestructura |

### VERTICAL: SENTYACHT

| Módulo | Función | Fase |
|---|---|---|
| **Catálogo público** | Web estática bilingüe (ES/EN) con fichas de barco | MVP |
| **Admin de barcos** | Panel interno para gestionar barcos, galerías, texto | MVP |
| **Build pipeline** | JSON → boats.js + HTML (generación estática) | MVP |
| **Landing de captación** | `/es/vender-mi-barco/` — formulario vendedores → lead engine | MVP (DONE) |
| **Landing de compra** | Página para compradores potenciales | Posterior |
| **Corporate site** | Web institucional de SentYacht | Posterior |

### AUTOMATIZACIÓN

| Módulo | Función | Fase |
|---|---|---|
| **n8n workflows** | Meta Lead Ads → webhook → lead engine | MVP |
| **Notificaciones** | WhatsApp/email automático al operador | Siguiente |
| **CRM sync** | Exportación a herramientas externas | Posterior |

## Dependencias entre bloques

```
Meta Ads ──→ n8n ──→ Webhook Intake ──→ Lead Engine ──→ Scoring
                                                          ↓
Web Form ──→ Public Intake ──→ Lead Engine          Operational Layer
                                                          ↓
                                                    Queue / Worklist
                                                          ↓
                                                    Operator (admin)
                                                          ↓
                                                    Status tracking
                                                          ↓
                                                    Delivery / Pack

Admin Panel ──→ Boat Data JSON ──→ Build Pipeline ──→ Static Site
```

## Fases

### Fase 1: MVP operativo (ACTUAL)
- Lead engine completo (ingesta, scoring, dedup, status)
- API con auth y rate limiting
- Catálogo público bilingüe (12 barcos)
- Admin panel para gestión de barcos
- Deploy en VPS con Caddy
- n8n interface documentada

### Fase 2: Activación comercial
- n8n workflow Meta Ads activado y probado con leads reales
- Landing de captación vendedores (`/es/vender-mi-barco/` — DONE)
- Notificaciones automáticas (WhatsApp o email al operador)
- Rescore de leads existentes con scoring final

### Fase 3: Optimización operativa
- Dashboard de métricas (leads/día, score distribution, conversion)
- Automatización de follow-up (contactar leads score alto)
- A/B testing de landing pages
- Market data layer (precios de referencia)

### Fase 4: Escalado
- Segunda vertical (inmobiliario, vehículos, otro)
- Multi-tenant lead engine
- Scoring configurable por vertical
- CRM integrations

## Core vs Vertical

**Core reusable** (apps/api/): Lead engine, scoring, operational layer, auth, schemas. Esto se reutiliza en cualquier vertical sin cambios.

**Vertical SentYacht** (static/site/, tools/, deploy/): Catálogo de barcos, admin de barcos, web pública, deploy configs. Esto es específico de yates.

**Línea divisoria**: si un cambio solo tiene sentido para barcos, va en la vertical. Si tiene sentido para cualquier negocio de leads, va en core.

## MVP vs Posterior

**Ya en MVP**: todo lo del lead engine, catálogo público, admin de barcos, deploy

**Siguiente bloque natural**: activación de n8n con Meta Ads (primer lead real automatizado)

**Posterior**: dashboard, notificaciones, second vertical, market data

## Monetización vs Infraestructura

**Monetización directa**: catálogo público (genera leads de compradores), landing de vendedores (genera leads de armadores)

**Infraestructura**: lead engine, scoring, admin panel, deploy pipeline, pathway discovery

## Operativo vs Estratégico

**Operativo** (mantiene el negocio funcionando): admin de barcos, deploy, backup, health checks

**Estratégico** (abre capacidad nueva): n8n activation, landing pages, notificaciones, scoring improvements
