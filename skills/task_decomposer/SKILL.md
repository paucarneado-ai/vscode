# Task Decomposer

## Propósito
Descomponer cualquier tarea en pasos pequeños, secuenciales y verificables antes de escribir código.

## Cuándo usarla
- Al recibir cualquier tarea que implique más de un cambio en el código.
- Cuando un paso no está claro o tiene dependencias implícitas.

## Reglas de comportamiento
1. Antes de tocar código, listar todos los pasos necesarios.
2. Cada paso debe ser completable y verificable de forma independiente.
3. Cada paso debe ser pequeño, concreto y verificable. Un paso puede tocar varios archivos si forman una única unidad lógica mínima.
4. Ordenar los pasos por dependencia: lo que no depende de nada va primero.
5. Si un paso falla 2 veces, parar y replantear el enfoque antes de reintentar.
6. No avanzar al paso siguiente sin verificar que el actual funciona.

## Salida esperada
Lista numerada de pasos con este formato:

- **Paso N**: Qué hacer
  - **Archivo(s)**: archivo(s) afectado(s)
  - **Verificación**: cómo confirmar que el paso está completo
