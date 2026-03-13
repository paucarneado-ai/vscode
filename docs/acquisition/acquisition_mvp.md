# Captación MVP — Arquitectura y Decisiones

**Estado:** MVP inicial
**Última actualización:** 2026-03-13

---

## Decisión de vertical y subcaso

**Vertical:** Barcos
**Subcaso principal:** Vendedor de barco de ocasión
**Subcaso secundario (siguiente bloque):** Comprador de barco

**Por qué vendedor primero:**
- Lado de oferta — sin barcos no hay negocio
- Tenemos empresa real de barcos para validar end-to-end
- El operador puede evaluar calidad del lead inmediatamente
- Feedback loop corto: lead entra → operador lo ve → dice si es útil o no

**Por qué barcos y no otra vertical:**
- Acceso a operador real para pruebas inmediatas
- Capacidad de cerrar el loop completo: captación → ingesta → evaluación → feedback
- Validación comercial más rápida que un caso teórico
- El patrón (landing + webhook + motor de leads) es 100% reutilizable para otras verticales después

---

## Circuito de captación MVP

```
[Meta Ad / Link directo / Contacto]
         |
         v
[Landing HTML mínima — vendedor de barco]
  - Formulario con campos ricos
  - POST a webhook
         |
         v
[POST /leads/webhook/landing-barcos-venta]
  - source = "webhook:landing-barcos-venta"
  - name, email del formulario
  - notes = campos estructurados serializados como texto
         |
         v
[Motor de leads existente]
  - scoring, dedup, actionable, queue, instruction
         |
         v
[Operador real revisa en queue/worklist]
  - Feedback: ¿lead útil? ¿info suficiente? ¿barco real?
```

---

## Source conventions de captación

| Source | Caso | Estado |
|---|---|---|
| `webhook:landing-barcos-venta` | Vendedor de barco de ocasión | Activo |
| `webhook:landing-barcos-compra` | Comprador de barco | Futuro (siguiente bloque) |

Sigue la convención existente `webhook:{provider}`. El provider identifica: canal + vertical + subcaso.

---

## Compromiso táctico: campos ricos en `notes`

El formulario de vendedor captura campos ricos (tipo de barco, eslora, marca, año, precio, etc.) que no existen como columnas en el schema persistido de leads (id, name, email, source, notes, score, created_at).

**Decisión:** serializar los campos ricos como texto estructurado dentro de `notes` en lugar de tocar schema persistido.

**Esto es un compromiso táctico de MVP**, no una solución ideal de largo plazo:
- **Ventaja:** no requiere migración de schema, el operador puede leer notes directamente, es parseable si se necesita más adelante.
- **Limitación:** no se puede filtrar, ordenar ni hacer queries por campos individuales (tipo de barco, eslora, precio). El scoring no puede usar estos campos.
- **Condición de reapertura:** cuando se necesite filtrar/buscar por campos de barco, o cuando el scoring necesite señales del formulario, evaluar añadir columnas al schema o un modelo de datos estructurado separado.

---

## Métricas mínimas de esta fase

Sin tracking externo, medibles con el sistema actual:
- Leads con `source = webhook:landing-barcos-venta` (via `GET /leads?source=webhook:landing-barcos-venta`)
- Duplicados detectados (409 en webhook)
- Score distribution y next_action distribution (via `/leads/summary`)
- Feedback cualitativo del operador: ¿leads reales? ¿info suficiente? ¿barcos vendibles?

---

## Piezas implementadas vs diseñadas vs fuera de alcance

### Implementado ahora
- Este documento de circuito de captación
- Brief del caso vendedor (`brief_barcos_venta.md`)
- Landing HTML funcional con formulario → webhook (`static/landing-barcos-venta.html`)

### Diseñado (no implementado)
- Caso comprador (segundo bloque, patrón casi idéntico)
- Tracking de conversión (requiere analytics externo)
- A/B testing de landings
- Meta Ads campaign config
- Parsing estructurado de notes a campos separados
- Scoring que use señales del formulario (tipo, eslora, precio)

### Fuera de alcance
- Tocar schema persistido de leads
- CMS, web corporativa
- Meta/Google Ads API integration
- Múltiples verticales simultáneas
- CRM, email marketing, analytics dashboard
- Attribution model completo
