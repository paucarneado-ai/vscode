# OpenClaw

Base modular orientada a automatizaciones y pipelines AI-first.

## MVP actual

Foco del MVP: flujo mínimo de leads en 4 pasos.

Lead Intake → Scoring → Lead Pack → Delivery

1. **Lead Intake** — Recibir datos de un lead
2. **Scoring** — Puntuar automáticamente el lead
3. **Lead Pack** — Generar un resumen estructurado del lead
4. **Delivery** — Entregar el Lead Pack generado

Sin WhatsApp avanzado, sin CRM complejo, sin booking, sin frontend.

## Estructura del proyecto

```text
OpenClaw/
├── .claude/          # Configuración de Claude Code (agentes, comandos, reglas)
├── .devcontainer/    # Dev container para VS Code + Docker
├── apps/             # Aplicaciones (API, workers)
├── services/         # Lógica de negocio
├── schemas/          # Esquemas de datos
├── tests/            # Tests
├── scripts/          # Scripts de utilidad
├── docs/             # Documentación
├── prompts/          # Prompts reutilizables
├── skills/           # Skills de Claude Code
└── docker-compose.yml
