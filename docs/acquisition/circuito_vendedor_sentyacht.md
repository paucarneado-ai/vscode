# Circuito de captación — Vendedor de embarcación (Sentyacht)

Fecha: 2026-03-13
Capa: vertical-specific (Sentyacht)
Estado: cerrado provisionalmente para validación real

## Flujo del propietario

```
Home corporativa (static/site/index.html → /)
  → CTA "Solicitar valoración y asesoramiento" (#contacto)
  → Bloque contacto → enlace a /vender/
  → Landing vendedor (static/site/vender/index.html → /vender/)
  → Formulario: nombre, teléfono, email, tipo, eslora [+ opcionales]
  → POST /api/leads/webhook/landing-barcos-venta
  → Motor de leads: normalización, dedupe, scoring, persistencia
  → Revisión operativa interna
```

Fuente única de la landing: `static/site/vender/index.html`. Para dev local, sobreescribir `API_BASE` con `window.OPENCLAW_API_BASE = "http://localhost:8000"`.

## Piezas del circuito

| Pieza | Archivo | Ruta pública | Función |
|---|---|---|---|
| Home corporativa | `static/site/index.html` | `/` | Posicionamiento, confianza, derivación al formulario |
| Landing vendedor | `static/site/vender/index.html` | `/vender/` | Captación directa del lead vendedor |
| Webhook endpoint | `POST /api/leads/webhook/landing-barcos-venta` | — | Ingesta del lead en el motor |
| Motor de leads | `apps/api/routes/leads.py` | — | Normalización, dedupe, scoring, persistencia |

## Coherencia verificada

- CTA text idéntico en home y landing: "Solicitar valoración y asesoramiento"
- Credenciales consistentes: +50 años, Puerto Deportivo del Masnou, red sur de Europa
- Timeframe consistente: 24–48 horas en ambas piezas
- Tono formal "usted" en ambas
- Webhook path correcto y funcional
- Subheadline de landing actualizada para coherencia tonal con home optimizada

## Checklist de publicación

### Bloqueos — no publicar sin resolver

| # | Elemento | Dónde | Acción |
|---|---|---|---|
| B1 | `API_BASE` configurado | Resuelto — `static/site/vender/index.html` usa `/api` por defecto | Verificar que Caddy hace strip de `/api` correctamente |
| B2 | Hosting no decidido | — | Decidir dónde se sirven las piezas estáticas (GitHub Pages, VPS, Netlify, etc.) |
| B3 | API no desplegada en producción | — | Desplegar FastAPI con el endpoint webhook accesible desde internet |

Sin B1+B2+B3 resueltos, el formulario no funciona y las páginas no tienen URL pública.

### Pendientes recomendables — publicable sin ellos pero débil

| # | Elemento | Dónde | Acción |
|---|---|---|---|
| P1 | Teléfono placeholder | `index.html` L159, placeholder `+34 937 52 12 34` | Reemplazar con número real de Sentyacht |
| P2 | Email placeholder | `index.html` L163, placeholder `info@sentyacht.com` | Verificar que el buzón existe y recibe correo |
| P3 | Apellido de Jordi | `index.html` L49, dice solo "Jordi" | Añadir apellido cuando se confirme |
| P4 | API sin autenticación | Endpoint webhook abierto | Aceptable para validación privada; añadir API key antes de tráfico público |

### Validación funcional — ejecutar tras resolver bloqueos

- [ ] Abrir home en URL pública → navegar hasta contacto → clic en CTA → verificar que llega a landing
- [ ] Rellenar formulario con datos de prueba → verificar que el lead aparece en `GET /leads?source=webhook:landing-barcos-venta`
- [ ] Enviar mismo email dos veces → verificar que muestra éxito (409 se trata como OK en el frontend)
- [ ] Probar en móvil real: home responsive + landing responsive + formulario usable + menú hamburguesa
- [ ] Verificar que teléfono y email de contacto funcionan (si son reales)

### Post-publicación — tras validación con tráfico real

- [ ] Verificar que llegan leads reales al motor
- [ ] Confirmar que alguien del equipo revisa y contacta al propietario en 24–48h
- [ ] Recoger feedback del primer propietario que complete el circuito
- [ ] Evaluar conversión: ¿el formulario convierte o el copy necesita ajuste?
- [ ] Decidir si se necesita analytics/tracking antes de abrir campañas

## Limitaciones conocidas

- Landing usa CSS inline, no comparte tokens con la home. Cambios de marca requieren actualización manual en ambos archivos.
- Color del botón CTA difiere: gold en home, navy en landing. Inconsistencia visual menor.
- No hay analytics, pixels ni tracking de conversión. Suficiente para validación manual; necesario antes de campañas de pago.
- No hay página de error dedicada si el API está caído. La landing muestra "Error de conexión" inline.
- No hay confirmación por email al propietario tras el envío.

## Operativa de primeros leads — checklist para el operador

### Revisión diaria (primeras semanas)

```
curl https://sentyacht.com/api/leads?source=webhook:landing-barcos-venta
```

Por cada lead nuevo:

1. ¿Tiene nombre, email, teléfono y tipo de embarcación? → Si falta algo, el formulario tiene un bug.
2. ¿Es un lead real o basura? → Si llegan leads sin sentido, activar honeypot/rate limit.
3. Contactar al propietario por teléfono en las primeras 24-48h (compromiso público de la web).
4. Registrar resultado del contacto: ¿respondió? ¿interesado? ¿datos coherentes con lo enviado?
5. Si el propietario dice que no recibió confirmación o no entendió qué esperar → flag para mejorar UX post-envío.

### Señales de que el circuito funciona (sin analytics)

| Señal | Cómo medirla | Frecuencia |
|---|---|---|
| Llegan leads | `GET /api/leads?source=webhook:landing-barcos-venta` — count | Diaria |
| Leads tienen datos útiles | Revisar campo notes — ¿tipo, eslora, teléfono presentes? | Cada lead |
| Propietario responde al contacto | Feedback directo del operador | Cada lead |
| No llega basura | Proporción leads reales vs spam | Semanal |
| Formulario funciona | Test manual: enviar lead de prueba | Semanal |

### Señales de alerta

- 0 leads en 2 semanas con URL compartida → verificar que el formulario funciona y la API responde.
- Más de 50% de leads son basura → activar honeypot + rate limit urgente.
- Propietarios dicen que "no sabían qué esperar" tras enviar → mejorar mensaje de éxito o añadir email de confirmación.
- Propietarios no reciben llamada en 48h → problema operativo, no técnico.

## Decisiones

- D1: Subheadline de landing actualizada para coherencia tonal con home optimizada. La versión anterior era el copy descartado del hero de la home.
- D2: La diferencia de color del botón CTA (gold vs navy) se documenta como follow-up, no como bloqueo. No justifica rehacer los estilos inline de la landing en esta fase.
- D3: La landing permanece standalone (sin nav ni enlace de retorno a home). Decisión de conversión: menos distracciones = más foco en el formulario.
- D4: Comentario de configuración ampliado en landing (API_BASE) para que quien publique sepa exactamente qué cambiar.
- D5: Landing única en `static/site/vender/index.html` con API_BASE="/api". Duplicado eliminado. Dev local usa override `window.OPENCLAW_API_BASE`.
- D6: CTA de home apunta a `/vender/` (ruta absoluta). Coherente con estructura de serving bajo un solo dominio.
- D7: Honeypot anti-bot en landing (campo oculto `website`). Si un bot lo rellena, se muestra éxito falso sin enviar al backend. Rate limiting documentado para Caddy en deploy plan.
