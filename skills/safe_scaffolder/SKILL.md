# Safe Scaffolder

## Propósito
Crear estructura de archivos y carpetas mínima y segura para nuevos módulos o funcionalidades, sin meter lógica innecesaria.

## Cuándo usarla
- Al crear un módulo, servicio o componente nuevo desde cero.
- Cuando el usuario pide generar estructura base para una funcionalidad.

## Reglas de comportamiento
1. Crear solo los archivos estrictamente necesarios para que el módulo funcione. Nada más.
2. No incluir lógica de negocio, datos de ejemplo ni código placeholder tipo "TODO: implement".
3. No crear archivos de configuración, utils ni helpers salvo que el usuario lo pida explícitamente.
4. Respetar la estructura y convenciones existentes del proyecto. No inventar patrones nuevos.
5. No agregar dependencias nuevas. Si el scaffolding las requiere, avisar antes de proceder.
6. Nunca hardcodear secretos, credenciales ni valores de configuración. Usar variables de entorno.
7. Incluir validación de inputs si el módulo expone un endpoint o boundary externo.

## Salida esperada
Antes de crear archivos, presentar:

- **Archivos a crear**: lista completa con rutas
- **Convención seguida**: qué patrón existente del proyecto se está replicando
- **Archivos que NO se crean**: qué se omite y por qué

Esperar confirmación del usuario antes de escribir si el scaffolding implica múltiples archivos, nueva estructura o decisiones no triviales.
