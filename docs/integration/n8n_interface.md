# Interfaz oficial OpenClaw -> n8n

Fecha: 2026-03-13
Fase: MVP staging

## Principio de arquitectura

```
OpenClaw = fuente de verdad + logica core (scoring, prioridad, contratos)
n8n      = capa externa de automatizacion/integracion/orquestacion
```

n8n **consume** OpenClaw via API. Nunca replica, recalcula ni contradice la logica core.

## Endpoints oficiales para automatizacion

### 1. Cola prioritizada — revision diaria

```
GET /api/internal/queue
GET /api/internal/queue?source=webhook:landing-barcos-venta
GET /api/internal/queue?limit=10
```

**Uso:** endpoint principal para saber que leads necesitan atencion, ordenados por urgencia.

**Campos estables en esta fase:**

| Campo | Tipo | Significado |
|---|---|---|
| lead_id | int | ID unico del lead |
| name | str | Nombre del contacto |
| source | str | Origen (webhook:landing-barcos-venta, etc.) |
| score | int | Score calculado por OpenClaw |
| rating | str | low / medium / high |
| next_action | str | Accion recomendada por OpenClaw |
| instruction | str | Instruccion legible para humano |
| alert | bool | true = requiere atencion urgente |
| created_at | str | Fecha de creacion del lead |

**Campos de respuesta global:** `total`, `urgent_count`, `generated_at`

**Patron n8n:** polling periodico (cada 5-15 min). Comparar `total` o max `lead_id` con el valor anterior para detectar cambios.

### 2. Detalle completo de un lead

```
GET /api/leads/{id}/pack
```

**Uso:** cuando n8n necesita contexto completo para una notificacion o un envio.

**Campos estables adicionales respecto a queue:** `email`, `notes` (contiene datos del barco: tipo, eslora, marca, precio, puerto, etc.)

**Patron n8n:** fetch on-demand solo cuando se necesita detalle. No polling.

### 3. Estadisticas rapidas

```
GET /api/leads/summary
GET /api/leads/summary?source=webhook:landing-barcos-venta
```

**Uso:** vision agregada para reportes o dashboards.

**Campos:** `total_leads`, `average_score`, `low_score_count`, `medium_score_count`, `high_score_count`, `counts_by_source`

**Patron n8n:** consulta diaria para resumen.

### 4. Listado de leads recientes

```
GET /api/leads?limit=N
GET /api/leads?source=X&limit=N
GET /api/leads?q=texto
```

**Uso:** busqueda flexible, deteccion de nuevos leads por ID descendente.

**Patron n8n:** `GET /api/leads?limit=1` para obtener el lead mas reciente y su `id`. Comparar con el ultimo `id` conocido para detectar nuevas entradas.

### 5. Export

```
GET /api/leads/export.csv
```

**Uso:** backup operativo o carga en hoja de calculo.

**Patron n8n:** cron semanal, guardar CSV en Google Drive / email.

### 6. Health check

```
GET /api/health
```

**Uso:** monitoreo basico de disponibilidad.

**Patron n8n:** polling cada 5 min. Si falla, alerta.

### 7. Ingesta externa canonica

```
POST /api/leads/external
```

**Uso:** adapter canonico para ingesta externa generica. Acepta phone y metadata ademas de los campos base. Recomendado sobre `/leads/webhook/{provider}` para nuevas integraciones que no necesitan un provider dedicado.

**Body:** `{name, email, source, phone?, notes?, metadata?}`

**Source:** debe seguir formato `tipo:identificador` (ej. `n8n:captacion`, `landing:barcos-venta`). Bare words rechazados con 422.

**Respuesta:** `{status: "accepted"|"duplicate", lead_id, score, message}`. Duplicados devuelven 409.

**Patron n8n:** HTTP Request node con POST, body JSON. Verificar `status` en respuesta para distinguir aceptado vs duplicado.

## Endpoints NO recomendados para n8n

| Endpoint | Razon |
|---|---|
| POST /api/leads | Reservado para integraciones directas con contrato source explicito. Preferir POST /api/leads/external para nuevas integraciones. |
| GET /api/leads/actionable | Redundante con queue para automatizacion. Queue ya tiene priorizacion. |
| GET /api/leads/actionable/worklist | Util para consumo humano, no para n8n (agrupacion innecesaria para bots). |
| GET /api/leads/{id}/delivery | Contrato de delivery, no de automatizacion. |

## Lo que n8n NO debe hacer

1. **No calcular scoring propio.** El score lo define OpenClaw. n8n lo consume tal cual.
2. **No asignar prioridad propia.** La prioridad viene de `alert`, `next_action` y el orden de queue.
3. **No mantener segunda fuente de verdad.** No guardar leads en una DB propia ni en un spreadsheet como fuente primaria.
4. **No reescribir logica de negocio.** Si n8n filtra leads, debe usar los campos de OpenClaw (score, alert, next_action), no inventar criterios propios.
5. **No mutar estado en OpenClaw** (en esta fase no hay endpoints de mutacion post-creacion).
6. **No hacer dedup propia.** La dedup la hace OpenClaw en ingesta.

## Automatizaciones MVP recomendadas

### A. Notificacion de lead nuevo

**Objetivo:** cuando entra un lead nuevo desde la landing, avisar inmediatamente al equipo.

| Aspecto | Detalle |
|---|---|
| Trigger | Cron cada 5 minutos |
| Paso 1 | `GET /api/leads?limit=1` -- obtener lead mas reciente |
| Deteccion | Comparar `id` con el ultimo id conocido (almacenado en n8n como variable estatica) |
| Paso 2 | Si hay nuevo: `GET /api/leads/{id}/pack` -- obtener detalle completo |
| Output | Mensaje con: nombre, email, telefono (extraer de notes), tipo de barco, eslora, score, next_action |
| Canal | Telegram / Email / WhatsApp Business (lo que este configurado) |
| Campos consumidos | De leads: `id`. De pack: `name`, `email`, `notes`, `score`, `next_action`, `alert` |
| Riesgo | Bajo. Solo lectura. Si n8n falla, no se pierde el lead (esta en OpenClaw). |
| Por que n8n | Es orquestacion pura: detectar evento + formatear + enviar a canal externo. No hay logica de negocio. |

**Ejemplo de mensaje:**

```
Nuevo lead en Sentyacht

Nombre: didac senties
Email: didacsenties93@gmail.com
Telefono: +34622205223
Tipo: Lancha a motor
Eslora: 18m
Marca: Azimut 62
Score: 60 (medium)
Accion: send_to_client

Ver detalle: http://76.13.48.227:8080/api/leads/3/pack
```

### B. Resumen diario de cola

**Objetivo:** cada manana, enviar un resumen del estado actual de leads pendientes.

| Aspecto | Detalle |
|---|---|
| Trigger | Cron diario a las 09:00 |
| Paso 1 | `GET /api/leads/summary` -- estadisticas globales |
| Paso 2 | `GET /api/internal/queue?limit=5` -- top 5 por prioridad |
| Output | Mensaje resumen con: total leads, urgentes, top 5 por prioridad con nombre y accion |
| Canal | Mismo canal que notificacion de lead nuevo |
| Campos consumidos | De summary: `total_leads`, `urgent_count`, `counts_by_source`. De queue items: `name`, `score`, `next_action`, `alert` |
| Riesgo | Bajo. Solo lectura. |
| Por que n8n | Agregacion + formato + envio periodico. Cero logica de negocio. |

**Ejemplo de mensaje:**

```
Resumen diario Sentyacht -- 2026-03-14

Total leads: 5
Urgentes: 5
Fuentes: landing-barcos-venta (4), staging-test (1)

Top 5 por prioridad:
1. didac senties -- score 60 -- send_to_client
2. Test Captacion Real -- score 60 -- send_to_client
3. ...
```

## Estabilidad del contrato

**Campos marcados como estables:** todos los listados en las tablas de arriba. No se eliminaran ni cambiaran de tipo sin aviso.

**Campos que pueden cambiar:** `instruction` (texto legible, puede cambiar de idioma o redaccion). `summary` (formato del string puede ajustarse).

**Campos que pueden aparecer en el futuro:** `status` (gestionado/cerrado), `assigned_to`, `last_contacted_at`. Seran aditivos, no romperan el contrato actual.

## Notas para quien implemente en n8n

- Base URL staging: `http://76.13.48.227:8080/api`
- No hay API key en esta fase (pendiente de implementar)
- Todas las respuestas son JSON excepto `/leads/export.csv`
- Los leads de la landing entran con source `webhook:landing-barcos-venta`
- Los datos del barco (tipo, eslora, marca, precio, puerto) estan dentro del campo `notes` como texto plano con formato `Clave: valor\n`
- Para extraer datos de notes en n8n: split por `\n`, luego split por `: ` para cada linea
- `alert: true` significa que el lead requiere atencion. Usarlo para decidir prioridad de notificacion, no reinventar
