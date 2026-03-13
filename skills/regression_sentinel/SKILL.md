# Regression Sentinel

## Propósito
Comprobar que lo que ya funciona no se rompe después de un cambio.

## Cuándo usarla
- Después de modificar código existente.
- Antes de dar por terminado un task que tocó funcionalidad ya implementada.
- Cuando un cambio afecta módulos compartidos o dependencias internas.

## Reglas de comportamiento
1. Antes de declarar un cambio completo, ejecutar los tests existentes relacionados.
2. Si no hay tests para el área afectada, advertir al usuario y proponer tests mínimos.
3. Verificar que los endpoints existentes siguen respondiendo con el mismo formato y status codes.
4. Si un test falla tras el cambio, no modificar el test para que pase. Investigar si el cambio introdujo un bug.
5. Comparar el comportamiento antes y después del cambio en los paths críticos.
6. Si el cambio toca scoring, leadpack o auth, aplicar verificación extra y escalar a revisión humana.

## Salida esperada
Después de ejecutar la verificación:

- **Tests ejecutados**: cuáles y resultado (pass/fail)
- **Endpoints verificados**: status y formato de respuesta
- **Regresiones detectadas**: descripción del problema, o "ninguna"
- **Acción recomendada**: continuar / investigar / escalar
