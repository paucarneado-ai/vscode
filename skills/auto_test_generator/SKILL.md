# Auto Test Generator

## Propósito
Proponer tests mínimos y útiles que cubran el happy path y los errores evidentes, sin generar suites masivas.

## Cuándo usarla
- Después de implementar o modificar una funcionalidad.
- Cuando el usuario pide tests para código existente.
- Antes de merge, para verificar cobertura mínima obligatoria.

## Reglas de comportamiento
1. Cubrir siempre: happy path, errores de validación de input y casos límite obvios.
2. No generar tests redundantes ni variaciones triviales del mismo caso.
3. Usar el framework y estilo de testing que ya exista en el proyecto. No introducir herramientas nuevas.
4. Tests deben ser deterministas y no depender de estado externo, orden de ejecución ni datos volátiles.
5. Elegir el nivel de aislamiento más simple que permita validar el comportamiento real sin complejidad innecesaria.
6. Cada test debe tener un nombre descriptivo que explique qué verifica.
7. Si el código no tiene tests previos, proponer solo los esenciales y confirmar alcance con el usuario.

## Salida esperada
Lista de tests propuestos con este formato:

- **Test N**: Qué verifica
  - **Tipo**: unitario / integración
  - **Input**: datos de entrada
  - **Expected**: resultado esperado

Esperar confirmación antes de escribir los tests.
