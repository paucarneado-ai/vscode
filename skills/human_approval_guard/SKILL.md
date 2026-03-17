# Human Approval Guard — ARCHIVED

> **Status: archived (2026-03-16)**
> Superseded by `.claude/CLAUDE.md` §10 (approval boundaries) + `apps/api/CLAUDE.md` REVIEW FLOW (risk classes + stop rules).
> All 6 approval categories below are fully covered by those governance layers.
> Retained for reference only. Do not treat as active governance.

## Propósito
Bloquear cambios críticos hasta recibir aprobación explícita del usuario.

## Cuándo usarla
Se evalúa antes de ejecutar cambios potencialmente críticos.

## Cambios que requieren aprobación
1. Modelos de datos: crear, modificar o eliminar tablas/esquemas.
2. Lógica de scoring: cualquier cambio en módulos o archivos de scoring.
3. Generación de Lead Pack: cualquier cambio en módulos o archivos de generación de Lead Pack.
4. Autenticación y autorización: cambios en autenticación, autorización, middleware de acceso o manejo de API keys.
5. Eliminación: borrar archivos, carpetas o tablas.
6. Infraestructura: cambios en docker-compose, Dockerfile o CI/CD.

## Reglas de comportamiento
1. Si un cambio entra en la lista anterior, NO ejecutar. Pedir aprobación primero.
2. Describir exactamente qué se va a modificar y por qué.
3. Esperar confirmación explícita ("sí", "aprobado", "dale"). No asumir aprobación implícita.
4. Si el usuario rechaza, proponer alternativa o detenerse.
5. Registrar en la respuesta qué cambio fue aprobado para trazabilidad.

## Salida esperada
Al detectar un cambio que requiere aprobación:

- **REQUIERE APROBACIÓN**
- **Tipo**: Categoría del cambio (modelo, scoring, eliminación, etc.)
- **Detalle**: Qué se va a hacer exactamente
- **Motivo**: Por qué se necesita este cambio
- Esperar respuesta del usuario antes de continuar.
