# SentYacht — Runbook operativo diario

## URLs

| Recurso | URL |
|---|---|
| Home | https://sentyacht.es/ |
| Landing vendedor | https://sentyacht.es/vender/ |
| API health | https://sentyacht.es/api/health |
| VPS staging directo | http://76.13.48.227:8080/ |

## Flujo de un lead

```
Visitante rellena formulario en /vender/
  → POST /api/leads/intake/web
  → scoring automático (30-100)
  → persistencia SQLite
  → respuesta al visitante: "Solicitud recibida"
```

## Operaciones diarias

### Ver leads nuevos (más recientes primero)

```bash
curl -s https://sentyacht.es/api/leads?source=web:sentyacht-vender&limit=10 | python -m json.tool
```

### Ver cola priorizada (score descendente, alertas primero)

```bash
curl -s https://sentyacht.es/api/internal/queue?limit=10 | python -m json.tool
```

### Ver detalle completo de un lead

```bash
curl -s https://sentyacht.es/api/leads/{id}/pack | python -m json.tool
```

### Ver estadísticas generales

```bash
curl -s https://sentyacht.es/api/leads/summary | python -m json.tool
```

### Exportar leads a CSV

```bash
curl -s https://sentyacht.es/api/leads/export.csv -o leads.csv
```

### Exportar solo leads de la landing

```bash
curl -s "https://sentyacht.es/api/leads/export.csv?source=web:sentyacht-vender" -o sentyacht-leads.csv
```

## Cómo interpretar la cola

| Score | Rating | Acción | Significado |
|---|---|---|---|
| 75-100 | high | send_to_client | Lead completo, alto valor. Contactar ya. |
| 50-74 | medium | send_to_client / review | Lead con datos parciales. Revisar antes de contactar. |
| 40-49 | low | review_manually | Datos mínimos. Evaluar si vale la pena contactar. |
| 30-39 | low | enrich_first | Sin datos útiles. Pedir más info o descartar. |

## Señales de scoring

| Señal | Puntos | Ejemplo |
|---|---|---|
| Base | 30 | Siempre |
| Tiene datos | +10 | Cualquier campo rellenado |
| Tipo alto valor | +10 | Yate, velero, catamarán |
| Eslora >= 10m | +10 | "12m", "40 pies" |
| Precio indicado | +15 | "850.000€" |
| Cada detalle extra | +5 (max 20) | Marca, año, puerto, precio |

## Detección de duplicados

Automática: mismo email + mismo origen → 409 (no se crea segundo lead).
El visitante ve "Solicitud recibida" igualmente (no se le penaliza).

## Troubleshooting

### API no responde

```bash
ssh root@76.13.48.227
systemctl status openclaw-api
journalctl -u openclaw-api --no-pager -n 20
systemctl restart openclaw-api
```

### Web no carga

```bash
ssh root@76.13.48.227
systemctl status caddy
curl -s http://127.0.0.1:8080/
systemctl restart caddy
```

### Backup de datos

```bash
ssh root@76.13.48.227
bash /home/openclaw/app/deploy/ops/backup-sqlite.sh
```

### Deploy de cambios

```bash
# Desde Windows (Git Bash)
cd ~/Desktop/OpenClaw
bash deploy/deploy-staging.sh 76.13.48.227
```
