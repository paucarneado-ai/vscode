# tasks/todo.md

## Active Task
Task: Auditoría y corrección de módulos leads — Fase 5 (reporting/consulta)

## Objective
Corregir 2 hallazgos de la auditoría de reporting: H15 (escapar wildcards LIKE en q) y H19 (normalizar source en query filter). Documentar H16, H17, H18.

## Plan
- [x] H15: escapar %, _ y \ en patrón LIKE de _build_where_clause
- [x] H19: normalizar source con strip().lower() en _build_where_clause
- [x] Tests: 7 nuevos (191 total, 0 fallos)
- [x] Documentación: decision log (D22)

## Review
### What changed
- `apps/api/routes/leads.py`: _build_where_clause — source normalizado, q escapa wildcards LIKE con ESCAPE '\'
- `tests/api/test_api.py`: +7 tests (H15: 3 tests, H19: 4 tests)
- `docs/leads_decision_log.md`: D22

### What was verified
- 191 tests pass (0 failures)
- q con % literal no actúa como wildcard (solo match exacto)
- q con _ literal no actúa como wildcard (solo match exacto)
- Escapado consistente en list, summary y CSV
- source filter case-insensitive y strip de whitespace
- source normalization consistente en list, summary y CSV
- All existing contracts preserved

### What was intentionally not changed
- H16 (CSV export sin created_at) — cambio de contrato, no implementado, ver nota de impacto abajo
- H17 (summary sin limit/offset) — diseño correcto, no problema
- H18 (q no busca en source) — source tiene filtro dedicado, no problema
- No schema changes
- No endpoint contract changes

### Nota de impacto H16 (CSV created_at)
Añadir `created_at` a `CSV_COLUMNS` cambiaría el contrato del export CSV:
- Añade una 7ª columna al final (id, name, email, source, score, notes, **created_at**)
- Consumidores que parseen por índice de columna (ej. `row[5]` para notes) no se romperían (la nueva columna va al final)
- Consumidores que parseen por número exacto de columnas (`assert len(row) == 6`) sí se romperían
- Consumidores que parseen por header name (`row["notes"]`) no se romperían
- El cambio es aditivo (no modifica columnas existentes ni su orden), pero sigue siendo un cambio de contrato observable
- Recomendación: implementar cuando haya un consumidor real que necesite la fecha, no de forma preventiva
