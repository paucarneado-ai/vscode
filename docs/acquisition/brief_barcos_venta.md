# Brief de Captación — Vendedor de Barco de Ocasión

**Vertical:** Barcos
**Subcaso:** Vendedor de barco de ocasión
**Source:** `webhook:landing-barcos-venta`
**Estado:** MVP inicial
**Última actualización:** 2026-03-13

---

## Oferta

Ayudamos al propietario a vender su barco sin complicaciones.
No cobramos por el contacto inicial. El propietario describe su barco y nosotros le contactamos.

---

## Variantes de copy

### Headlines
1. **"Vende tu barco sin complicaciones"** — directo, sin promesa inflada
2. **"¿Quieres vender tu barco? Te ayudamos"** — tono de servicio, más cercano
3. **"Ponemos tu barco delante de compradores reales"** — orientado a resultado

### Subheadlines
1. **"Cuéntanos sobre tu barco y te contactamos sin compromiso"** — bajo riesgo, CTA suave
2. **"Rellena el formulario y un especialista te contactará en 24h"** — expectativa concreta de respuesta
3. **"Describe tu barco en 2 minutos y empezamos a trabajar"** — facilidad y rapidez

### CTAs
1. **"Quiero vender mi barco"** — intención clara del usuario
2. **"Solicitar valoración gratuita"** — percepción de valor añadido
3. **"Enviar datos de mi barco"** — neutro, descriptivo, sin promesa

### Combinación recomendada para MVP (landing v1)
- Headline: "Vende tu barco sin complicaciones"
- Subheadline: "Cuéntanos sobre tu barco y te contactamos sin compromiso"
- CTA: "Quiero vender mi barco"

---

## Contrato del formulario

### Campos obligatorios

| Campo | ID | Tipo | Validación |
|---|---|---|---|
| Nombre | `name` | text | min 1 char |
| Teléfono | `phone` | tel | min 6 chars |
| Email | `email` | email | formato email |
| Tipo de barco | `boat_type` | select | Velero / Lancha / Catamarán / Otro |
| Eslora aproximada (m) | `approximate_length` | text | libre (ej: "12m", "40 pies") |

### Campos opcionales

| Campo | ID | Tipo | Nota |
|---|---|---|---|
| Marca y modelo | `brand_model` | text | libre |
| Año aproximado | `year` | text | libre (ej: "2015", "aprox 2010") |
| Puerto / ubicación | `mooring_location` | text | libre |
| Precio orientativo (€) | `asking_price` | text | libre (ej: "120.000€", "negociable") |
| Notas adicionales | `extra_notes` | textarea | cualquier info adicional |

---

## Mapping al pipeline actual

El webhook `POST /leads/webhook/landing-barcos-venta` acepta: `name`, `email`, `notes`.

**Mapping:**
- `name` → campo `name` del formulario
- `email` → campo `email` del formulario
- `notes` → serialización de todos los campos ricos como texto estructurado

### Formato de serialización en `notes`

```
Teléfono: {phone}
Tipo: {boat_type}
Eslora: {approximate_length}
Marca/modelo: {brand_model}
Año: {year}
Puerto: {mooring_location}
Precio orientativo: {asking_price}
Notas: {extra_notes}
```

Los campos opcionales vacíos se omiten. Esto es legible para el operador y parseable programáticamente si se necesita más adelante.

**Compromiso táctico:** esta serialización en `notes` es un compromiso MVP por no tocar schema persistido. Ver `acquisition_mvp.md` para condiciones de reapertura.

---

## Circuito operativo post-ingesta

1. Lead entra via webhook → `source = webhook:landing-barcos-venta`
2. Scoring placeholder asigna score (base 50, +10 si source==test, +10 si notes no vacío)
3. Con notes llenos, score mínimo = 60 → `next_action = send_to_client`, `alert = true`
4. Lead aparece en queue/worklist como urgente
5. Operador revisa notes, evalúa si el barco es vendible
6. Feedback: ¿lead real? ¿info suficiente? ¿barco interesante?

**Nota:** con el scoring placeholder actual, todos los leads de la landing tendrán score 60 (base 50 + 10 por notes no vacío) y serán `send_to_client`. Esto es correcto para MVP — todo lead de la landing merece atención del operador.

---

## Métricas de validación

| Métrica | Cómo medir | Umbral MVP |
|---|---|---|
| Leads recibidos | `GET /leads?source=webhook:landing-barcos-venta` | >0 (funciona) |
| Duplicados | 409 en webhook | Bajo = bien |
| Info suficiente | Feedback operador sobre notes | Operador puede actuar sin repreguntar |
| Leads reales | Feedback operador | >50% son propietarios reales |
| Barcos vendibles | Feedback operador | Al menos algunos son comercializables |

---

## Extensiones futuras (no implementar ahora)

- **Comprador:** segundo subcaso, mismo patrón, distinto formulario y source (`webhook:landing-barcos-compra`)
- **Scoring mejorado:** usar tipo de barco, eslora, precio como señales de scoring
- **Campos persistidos:** migrar campos ricos de notes a columnas o modelo estructurado
- **Tracking:** UTM params, conversion tracking, Meta pixel
- **A/B testing:** probar variantes de headline/CTA
