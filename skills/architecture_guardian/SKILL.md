# Architecture Guardian

## Propósito
Evitar sobreingeniería, cambios fuera de alcance y abstracciones prematuras.

## Cuándo usarla
- Antes de crear archivos, módulos o abstracciones nuevas.
- Cuando un cambio propuesto toca código fuera del alcance del task actual.
- Cuando se propone agregar una dependencia nueva.

## Reglas de comportamiento
1. Si el task dice "modificar scoring", no refactorizar también el router de leads.
2. No crear helpers, utils o abstracciones para algo que se usa una sola vez.
3. No agregar dependencias sin justificación explícita. Cada dependencia es deuda.
4. Tres líneas similares son mejor que una abstracción prematura.
5. No diseñar para requisitos hipotéticos futuros. Solo lo que se necesita ahora.
6. Si un cambio toca más de lo pedido, advertir al usuario antes de ejecutar.
7. No mover ni renombrar estructura existente sin motivo claro y sin avisar antes.

## Salida esperada
Antes de ejecutar un cambio que active alguna regla, emitir:

- **Alerta**: Qué regla se activó
- **Cambio propuesto**: Qué se iba a hacer
- **Alternativa**: Solución más simple que respeta el alcance
