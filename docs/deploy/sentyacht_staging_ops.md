# Staging operations — Sentyacht en Hostinger VPS

Fecha: 2026-03-13
Capa: bridging layer

## Acceso

```bash
ssh root@76.13.48.227
```

## URLs de staging

| Ruta | URL |
|---|---|
| Home | http://76.13.48.227:8080/ |
| Landing | http://76.13.48.227:8080/vender/ |
| API health | http://76.13.48.227:8080/api/health |
| Leads | http://76.13.48.227:8080/api/leads |

Caddy en `:8080` (Traefik ocupa `:80`).

## Directorios en el VPS

```
/home/openclaw/                  # Usuario openclaw
├── app/apps/                    # RUNTIME — código Python, systemd WorkingDirectory
├── venv/                        # RUNTIME — virtualenv Python
├── data/leads.db                # DATOS — SQLite (no tocar manualmente)
├── backups/                     # BACKUPS — snapshots de leads.db
├── deploy/                      # CONFIGS — Caddyfile, systemd unit, scripts ops
│   ├── ops/                     #   check-staging.sh, restart-services.sh, backup-sqlite.sh
│   ├── systemd/                 #   openclaw-api.service
│   └── Caddyfile.sentyacht      #   Caddyfile de producción (no usado en staging)
├── .env                         # SECRETS — DATABASE_PATH, etc.
│
├── apps/                        # WORKSPACE — copia del repo (git clone original)
├── tests/                       #   tests del repo
├── docs/                        #   documentación del repo
├── .git/                        #   historial git
└── ...                          #   resto del repo

/home/sentyacht/                 # Usuario sentyacht (vertical-specific)
└── site/                        # WEB ESTÁTICA — Caddy file_server root
    ├── index.html               #   Home → /
    ├── css/                     #   brand.css, layout.css, components.css
    └── vender/index.html        #   Landing → /vender/
```

**Convención:** `deploy-staging.sh` despliega desde el repo local al VPS. No se edita código directamente en `app/` — siempre se redespliega desde local. El workspace (`apps/`, `tests/`, `.git/`) es para inspección y debug, no para servir.

## Flujo de trabajo remoto con tmux

```bash
# 1. Conectar al VPS
ssh root@76.13.48.227

# 2. Abrir sesión persistente (o reconectar)
tmux new -s oc           # primera vez
tmux attach -t oc        # reconectar tras desconexión

# 3. Health check rápido
bash /home/openclaw/deploy/ops/check-staging.sh

# 4. Ver logs en tiempo real (panel separado: Ctrl-b + %)
journalctl -u openclaw-api -f

# 5. Inspeccionar leads
curl -s http://127.0.0.1:8080/api/leads | python3 -m json.tool

# 6. Inspeccionar un lead pack
curl -s http://127.0.0.1:8080/api/leads/1/pack | python3 -m json.tool

# 7. Backup antes de cambios
bash /home/openclaw/deploy/ops/backup-sqlite.sh

# 8. Si algo falla, reiniciar servicios
bash /home/openclaw/deploy/ops/restart-services.sh

# 9. Desconectar tmux sin cerrar (Ctrl-b + d)
# La sesión sigue corriendo. Reconectar con: tmux attach -t oc
```

### Tmux — mínimo útil

| Acción | Atajo |
|---|---|
| Dividir horizontal | `Ctrl-b %` |
| Dividir vertical | `Ctrl-b "` |
| Cambiar panel | `Ctrl-b flechas` |
| Desconectar | `Ctrl-b d` |
| Cerrar panel | `exit` o `Ctrl-d` |
| Listar sesiones | `tmux ls` |

## Redeploy desde local

Desde Git Bash en la raíz del repo:
```bash
./deploy/deploy-staging.sh 76.13.48.227
```

El script sincroniza código, estáticos, configs y ops scripts, instala deps, reinicia servicios y valida 5 endpoints.

## Scripts operativos

Todos en `/home/openclaw/deploy/ops/`, ejecutar como root en el VPS:

```bash
# Health check completo (servicios + endpoints + DB)
bash /home/openclaw/deploy/ops/check-staging.sh

# Reiniciar API y Caddy
bash /home/openclaw/deploy/ops/restart-services.sh

# Backup de SQLite
bash /home/openclaw/deploy/ops/backup-sqlite.sh
```

## Logs

```bash
# API (uvicorn)
journalctl -u openclaw-api -f
journalctl -u openclaw-api --no-pager -n 50

# Caddy
journalctl -u caddy -f
journalctl -u caddy --no-pager -n 50
```

## Troubleshooting

```bash
# API no responde
systemctl status openclaw-api
journalctl -u openclaw-api --no-pager -n 20

# Caddy no responde
systemctl status caddy
cat /etc/caddy/Caddyfile

# Puerto ocupado
ss -tlnp | grep -E ":(8000|8080)"

# DB corrupta
sqlite3 /home/openclaw/data/leads.db "PRAGMA integrity_check"

# Limpiar leads de staging
sqlite3 /home/openclaw/data/leads.db "DELETE FROM leads WHERE source = 'webhook:staging-test'"
```
