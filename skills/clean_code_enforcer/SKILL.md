# Clean Code Enforcer

## Propósito
Mantener el código legible, con responsabilidades claras, sin duplicación innecesaria y sin código muerto.

## Cuándo usarla
- Al escribir código nuevo.
- Al modificar código existente.
- En revisiones antes de commit o merge.

## Reglas de comportamiento
1. Cada función o módulo debe tener una responsabilidad clara. Si hace dos cosas, dividir.
2. No dejar código muerto: imports sin usar, funciones no referenciadas, variables asignadas pero nunca leídas. Eliminar, no comentar.
3. No duplicar lógica que ya existe en el proyecto. Reutilizar antes de reescribir.
4. Nombres descriptivos que expliquen qué hace el código, no cómo. Evitar abreviaturas crípticas.
5. No añadir comentarios para explicar código confuso. Reescribir el código para que sea claro.
6. No refactorizar código fuera del alcance del task actual. Solo limpiar lo que se está tocando.
7. Respetar el formato y lint configurados en el proyecto. No introducir estilos propios.

## Salida esperada
Al detectar un problema de limpieza en código que se está tocando:

- **Problema**: Qué se encontró (código muerto, duplicación, nombre confuso, etc.)
- **Ubicación**: Archivo y línea
- **Corrección propuesta**: Cambio concreto
