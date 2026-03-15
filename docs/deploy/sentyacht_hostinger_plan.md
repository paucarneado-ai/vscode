# Plan de despliegue — Sentyacht en Hostinger VPS

Fecha: 2026-03-13
Capa: bridging layer (vertical-specific web + core reusable API)
Estado: plan documentado, no ejecutado

## Por qué Hostinger VPS y no Arsys hosting

Arsys ofrece hosting compartido orientado a WordPress/PHP. OpenClaw es una app Python (FastAPI + uvicorn) que necesita:
- proceso Python persistente (no CGI/PHP),
- control sobre reverse proxy,
- SQLite con acceso directo a filesystem.

Hostinger VPS da un servidor Linux completo con acceso root, suficiente para correr Caddy + uvicorn + archivos estáticos. Coste: ~5-10 EUR/mes para el plan básico.

## Arquitectura

```
sentyacht.com (Hostinger VPS, IP pública)
│
├─ Caddy (reverse proxy + HTTPS automático)
│   ├─ /              → archivos estáticos (web corporativa)
│   ├─ /vender        → archivo estático (landing vendedor)
│   └─ /api/*         → reverse proxy → localhost:8000
│
├─ uvicorn (FastAPI, puerto 8000, solo localhost)
│   └─ SQLite: /home/openclaw/data/leads.db
│
└─ systemd
    ├─ caddy.service  (reverse proxy)
    └─ openclaw.service (API)
```

### Decisiones de arquitectura

| Decisión | Elección | Razón |
|---|---|---|
| Reverse proxy | Caddy | HTTPS automático, config mínima (~15 líneas), redirect HTTP→HTTPS incluido |
| Todo bajo un dominio | Sí | Elimina CORS, simplifica certificados, API_BASE = "/api" |
| Process manager | systemd | Ya está en el VPS, sin dependencias extra, restart automático |
| Base de datos | SQLite en filesystem | MVP — sin PostgreSQL, sin contenedores, backup = copiar archivo |
| Docker | No | No aporta simplicidad real para un solo proceso Python en un solo servidor |

### Estructura de rutas

| Ruta pública | Qué sirve | Origen |
|---|---|---|
| `https://sentyacht.com/` | Web corporativa | `/home/sentyacht/site/index.html` + CSS |
| `https://sentyacht.com/vender/` | Landing vendedor | `/home/sentyacht/site/vender/index.html` |
| `https://sentyacht.com/api/health` | Health check | uvicorn → FastAPI |
| `https://sentyacht.com/api/leads/webhook/landing-barcos-venta` | Webhook captación | uvicorn → FastAPI |
| `https://sentyacht.com/api/*` | Resto de API | uvicorn → FastAPI |

### Caddyfile propuesto

```caddyfile
sentyacht.com {
    # Rate limiting en webhook — máx 5 requests/minuto por IP
    @webhook path /api/leads/webhook/*
    rate_limit @webhook {
        zone webhook_rl {
            key {remote_host}
            events 5
            window 1m
        }
    }

    # API — reverse proxy a uvicorn (strip /api prefix)
    handle /api/* {
        uri strip_prefix /api
        reverse_proxy localhost:8000
    }

    # Todo lo demás — archivos estáticos desde un solo root
    handle {
        file_server {
            root /home/sentyacht/site
        }
    }
}
```

Un solo `file_server` root en `/home/sentyacht/site/`. `/` sirve `index.html`, `/vender/` sirve `vender/index.html` automáticamente. Sin rewrites.

**Nota sobre rate limiting:** Caddy no incluye rate limiting nativo en la distribución estándar. Requiere el módulo `caddy-ratelimit` (build con `xcaddy`). Si no se quiere compilar Caddy custom, la alternativa es rate limiting a nivel de iptables o fail2ban. Evaluar en staging qué opción es más simple.

Caddy hace strip de `/api` antes de pasar a uvicorn, así el código Python no necesita cambios (sigue sirviendo en `/leads/webhook/...`).

### API_BASE en la landing

La landing (repo: `static/site/vender/index.html`, servidor: `/home/sentyacht/site/vender/index.html`) ya tiene `API_BASE = "/api"` por defecto.
Para desarrollo local, sobreescribir con `window.OPENCLAW_API_BASE = "http://localhost:8000"` antes de que cargue el script.

### SQLite en este MVP

- El archivo `.db` vive en `/home/openclaw/data/leads.db`.
- Backup: `cp leads.db leads.db.bak` o cron diario con `sqlite3 leads.db ".backup /home/openclaw/backups/leads_$(date +%Y%m%d).db"`.
- SQLite soporta el volumen de un MVP (decenas/cientos de leads). No es necesario migrar a PostgreSQL hasta que haya concurrencia real o volumen alto.
- Riesgo: si uvicorn corre con múltiples workers, SQLite puede dar errores de escritura concurrente. Solución MVP: correr uvicorn con `--workers 1`. Suficiente para este volumen.

### HTTPS

Caddy obtiene y renueva certificados de Let's Encrypt automáticamente. Requisitos:
- El dominio debe apuntar a la IP del VPS (registro A en DNS).
- Los puertos 80 y 443 deben estar abiertos en el firewall del VPS.
- No se necesita configuración adicional — Caddy lo gestiona solo.

### Estructura de archivos en el servidor

```
/home/openclaw/                  # Core reusable (backend OpenClaw)
├── app/
│   ├── apps/                    # código Python (FastAPI)
│   └── requirements.txt
├── venv/                        # virtualenv Python
├── data/
│   └── leads.db                 # SQLite
├── backups/                     # backups de SQLite
├── deploy/                      # configs de despliegue
│   ├── Caddyfile.sentyacht
│   └── systemd/
│       └── openclaw-api.service
└── .env                         # variables de entorno

/home/sentyacht/                 # Vertical-specific (web Sentyacht)
└── site/                        # Caddy file_server root
    ├── index.html               # → /
    ├── css/
    └── vender/
        └── index.html           # → /vender/
```

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| SQLite corrupción por escritura concurrente | Baja (1 worker) | Alto | uvicorn --workers 1, backup diario |
| Webhook abierto (spam/basura) | Media si URL pública | Medio | Honeypot en landing + rate limit en Caddy antes de go-live |
| VPS sin backup automático | Media | Alto | Cron de backup diario de SQLite + snapshot semanal del VPS |
| Caída de uvicorn | Baja | Medio | systemd con Restart=always |
| Certificado HTTPS falla | Muy baja | Medio | Caddy renueva automáticamente; verificar puertos 80/443 abiertos |
| Dominio mal apuntado | Baja | Alto | Probar con IP directa en staging antes de mover DNS |
