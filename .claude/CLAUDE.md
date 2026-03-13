# OpenClaw — Reglas de Proyecto para Claude Code

## Principios generales

- **MVP first**: Solo implementar lo necesario para el paso actual. No construir para casos futuros hipotéticos.
- **No sobreingeniería**: La solución más simple que funcione. Sin abstracciones prematuras.
- **Evitar loops**: Si un enfoque falla 2 veces, parar y replantear. No reintentar la misma solución.
- **Reducir deuda técnica**: Código limpio desde el inicio. No dejar TODOs sin ticket asociado.
- **No tocar código fuera de alcance**: Si el task es modificar scoring, no refactorizar también el router de leads.

## Estado actual del MVP

Persistencia: SQLite (archivo local).
Framework: FastAPI.
Tests: pytest con TestClient.

### Endpoints operativos

| Endpoint | Método | Estado |
|---|---|---|
| /health | GET | OK |
| /leads | POST | OK — normaliza source/email, dedup por email+source, 409 si duplicado |
| /leads | GET | OK — filtros: source, min_score, limit, offset, q (LIKE en name/email/notes) |
| /leads/{id} | GET | OK |
| /leads/{id}/pack | GET | OK — JSON con rating y summary |
| /leads/{id}/pack/html | GET | OK — HTML renderizado |
| /leads/{id}/pack.txt | GET | OK — texto plano |
| /leads/{id}/delivery | GET | OK — delivery JSON con pack embebido |

### Contratos aceptados

**POST /leads:**
- Normaliza source (strip + lower) y email (strip + lower) antes de persistir
- Deduplicación ligera: email + source (post-normalización). Duplicado devuelve 409 con body LeadCreateResult y meta.status = "duplicate"
- Scoring se calcula con source normalizado
- Respuesta 200: LeadCreateResult con meta.status = "accepted"

**GET /leads:**
- Query params opcionales: source (exact match), min_score (>= int, ge=0), limit (ge=1), offset (ge=0), q (LIKE %q% en name, email, notes)
- Todos combinables entre sí con AND
- ORDER BY id DESC siempre
- Offset sin limit usa LIMIT -1 (idiom SQLite)
- Params inválidos devuelven 422 (validación FastAPI con Query)

## Reglas de desarrollo

- Preferir tipado explícito y validación en los boundaries del sistema.
- Tests básicos obligatorios antes de merge: happy path + errores obvios + bordes simples.
- Usar herramientas de formato y lint de forma consistente en todo el proyecto.
- No introducir dependencias nuevas sin justificación clara. Cada dependencia es deuda.
- SQL siempre con bind params (?). Nunca interpolación.

## Reglas de seguridad

- Nunca hardcodear secretos. Usar variables de entorno via .env
- Validar todos los inputs en los boundaries (API endpoints)
- API key requerida en todos los endpoints

## Aprobación humana requerida

Estos cambios NO se ejecutan sin aprobación explícita:

- Cambios en modelos de datos o schema persistido (tabla leads, columnas)
- Cambios en lógica de scoring (services/scoring)
- Cambios en autenticación, autorización, API keys
- Eliminación de archivos, tablas o estructura existente
- Cambios en Docker, docker-compose, CI/CD
- Cambios en .claude/*, skills/*
- Dependencias nuevas
- Refactors que afecten a múltiples módulos
- Cambios incompatibles en contratos públicos de la API

## Triada (test + review + aprobación humana)

Solo se aplica en decisiones de alto impacto:

- Scoring engine (services/scoring)
- Generación de Lead Pack (services/leadpack)
- Autenticación y autorización

## Archivos protegidos

No tocar salvo petición explícita:
- README.md
- Dockerfile, docker-compose*
- .claude/*, skills/*
- .gitignore

## Comandos estándar de validación

```bash
python -m pytest tests/api/test_api.py -v   # suite API completa
python -m pytest tests/ -v                   # suite completa
ruff check .                                 # lint
ruff format .                                # formato
```

## Deuda técnica conocida

- Dedup por email+source es a nivel app, no a nivel DB (sin UNIQUE constraint). Race condition teórica en concurrencia alta. Aceptable para MVP con SQLite.
- LIKE search (q param) es case-insensitive solo para ASCII en SQLite. Suficiente para MVP.
- Wildcards de LIKE (%, _) no se escapan en q param. Riesgo bajo.

## Fases siguientes (orden recomendado)

1. API key auth mínima (requiere aprobación)
2. Scoring configurable / reglas extendidas (requiere aprobación)
3. Export CSV/JSON batch desde GET /leads
4. Webhooks o notificaciones de delivery
5. Market data layer con caché/fallback

## Automations MVP (futuro)

- Triada modo B: scoring_only como modo por defecto
- Subset configurable de reglas de scoring
- Triggers duros: condiciones que escalan automáticamente a revisión humana

## Market Data (futuro)

- Toda validación de datos de mercado debe ser determinista y reproducible
- No usar datos externos sin capa de caché/fallback
- Documentar fuente de datos en el código
- No requiere triada: validación determinista es suficiente
