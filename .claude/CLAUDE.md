# OpenClaw — Reglas de Proyecto para Claude Code

## Principios generales

- **MVP first**: Solo implementar lo necesario para el paso actual. No construir para casos futuros hipotéticos.
- **No sobreingeniería**: La solución más simple que funcione. Sin abstracciones prematuras.
- **Evitar loops**: Si un enfoque falla 2 veces, parar y replantear. No reintentar la misma solución.
- **Reducir deuda técnica**: Código limpio desde el inicio. No dejar TODOs sin ticket asociado.
- **No tocar código fuera de alcance**: Si el task es modificar scoring, no refactorizar también el router de leads.

## Reglas de desarrollo

- Preferir tipado explícito y validación en los boundaries del sistema.
- Tests básicos obligatorios antes de merge. No hace falta cobertura total, pero sí cubrir el happy path y los errores evidentes.
- Usar herramientas de formato y lint de forma consistente en todo el proyecto.
- No introducir dependencias nuevas sin justificación clara. Cada dependencia es deuda.

## Reglas de seguridad

- Nunca hardcodear secretos. Usar variables de entorno via .env
- Validar todos los inputs en los boundaries (API endpoints)
- API key requerida en todos los endpoints

## Aprobación humana

- Cambios en modelos de datos: requieren aprobación antes de ejecutar
- Cambios en lógica de scoring: requieren aprobación antes de ejecutar
- Eliminación de archivos o tablas: requieren aprobación antes de ejecutar
- Cambios en docker-compose o infraestructura: requieren aprobación antes de ejecutar

## Triada (test + review + aprobación humana)

Solo se aplica en decisiones de alto impacto:

- Scoring engine (services/scoring)
- Generación de Lead Pack (services/leadpack)
- Autenticación y autorización

## Automations MVP

- Triada modo B: scoring_only como modo por defecto
- Subset configurable de reglas de scoring
- Triggers duros: condiciones que escalan automáticamente a revisión humana

## Market Data

- Toda validación de datos de mercado debe ser determinista y reproducible
- No usar datos externos sin capa de caché/fallback
- Documentar fuente de datos en el código
- No requiere triada: validación determinista es suficiente
