# SentYacht Domain Setup — sentyacht.es

## Architecture

```
Browser → sentyacht.es (DNS)
       → Traefik :443 (SSL termination, Let's Encrypt)
       → Caddy :8080 (routing)
           /api/* → strip prefix → uvicorn :8000
           /*     → file_server /home/sentyacht/site/
```

## Current State (2026-03-17)

- **DNS**: sentyacht.es and www.sentyacht.es → 76.13.48.227
- **SSL**: Let's Encrypt via Traefik (auto-renewal)
- **Traefik config**: /etc/easypanel/traefik/config/main.yaml
- **Backup**: /etc/easypanel/traefik/config/main.yaml.bak.20260317-154321

## What was changed

Services `web-sentyacht_sentyacht-architecture-1` (sentyacht.es) and
`web-sentyacht_sentyacht-architecture-2` (www.sentyacht.es) in Traefik's
`main.yaml` were pointed from the Docker container to Caddy on the host:

```
Before: http://web-sentyacht_sentyacht-architecture:80/
After:  http://172.17.0.1:8080/
```

Traefik routers, TLS config, and all other services were NOT modified.

## Rollback

Immediate rollback (< 30 seconds, no downtime):

```bash
ssh root@76.13.48.227
cp /etc/easypanel/traefik/config/main.yaml.bak.20260317-154321 /etc/easypanel/traefik/config/main.yaml
```

Traefik picks up config changes automatically — no restart needed.

## Verification commands

```bash
# From outside
curl -s https://sentyacht.es/api/health
curl -s -o /dev/null -w "%{http_code}" https://sentyacht.es/vender/
curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}" http://sentyacht.es/

# From VPS
curl -sk -H "Host: sentyacht.es" https://127.0.0.1/api/health
```
