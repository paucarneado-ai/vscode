# Type Safety Guard

## Propósito
Asegurar contratos claros de entrada/salida y validación coherente en los boundaries del sistema, usando tipos explícitos cuando aporten valor real.

## Cuándo usarla
- Al definir o modificar endpoints, schemas o interfaces entre módulos.
- Cuando datos cruzan un boundary: API, base de datos, servicios externos.
- Al revisar código que manipula estructuras de datos compartidas.

## Reglas de comportamiento
1. Tipar explícitamente entradas y salidas en boundaries: endpoints, funciones públicas de servicios y schemas de validación.
2. No tipar por obsesión. Si el tipo es obvio por contexto o el código es interno y simple, no forzar anotaciones.
3. Validar inputs en el boundary donde entran al sistema. No re-validar en cada capa interna.
4. Los schemas de validación (Pydantic, etc.) son la fuente de verdad para los contratos. No duplicar validación manualmente.
5. Si una función devuelve estructuras distintas según el caso, unificar el contrato de retorno.
6. No usar `Any`, `dict` genérico o tipos sin estructura en boundaries. Ser explícito donde importa.
7. Cambios en schemas o modelos de datos requieren aprobación humana (escalar a Human Approval Guard).

## Salida esperada
Al detectar un problema de tipado o validación:

- **Problema**: Qué falta o es incoherente
- **Ubicación**: Archivo y línea
- **Corrección propuesta**: Tipo o validación concreta a aplicar
