# SentYacht — Arquitectura final de serving público

Fecha de cierre: 2026-03-18

## Cadena de routing

```
Browser -> sentyacht.es (DNS -> 76.13.48.227)
  -> Traefik :443 (SSL, gestionado por EasyPanel, auto-renewal Let's Encrypt)
    -> Docker container nginx :80 (proxy puro, gestionado por EasyPanel)
      -> Caddy :8080 (host, gestionado por OpenClaw)
        -> GET /* -> file_server /home/sentyacht/site/
        -> POST /api/leads/intake/web -> uvicorn :8000
        -> /api/* (todo lo demas) -> 403
```

## Fuente activa del frontend

```
/home/sentyacht/site/   (56 archivos)
```

Esta es la UNICA fuente de contenido web público. No hay otra.
Se despliega desde OpenClaw via `deploy/deploy-staging.sh`.

## Función del proxy Docker

El servicio EasyPanel `web-sentyacht_sentyacht-architecture` es un nginx
reverse proxy transparente. Su unica función es recibir tráfico de Traefik
y reenviarlo a Caddy en el host.

Archivos funcionales (en EasyPanel):
```
/etc/easypanel/projects/web-sentyacht/sentyacht-architecture/code/
  Dockerfile          # nginx:alpine + proxy config
  nginx-proxy.conf    # proxy_pass http://172.17.0.1:8080
  README.md           # documentacion
```

NO contiene contenido web. NO debe editarse salvo cambio de infraestructura.

## Backups (archivo de seguridad, no fuente activa)

```
/home/sentyacht/backup-web-legacy/    # web legacy original pre-adaptacion
/home/sentyacht/site-simple-backup/   # web simple anterior de OpenClaw
```

Estos directorios son archivo de rescate. No se sirven, no se enlazan,
no deben convertirse en fuente activa.

## Qué NO debe volver a editarse por error

- `/etc/easypanel/projects/web-sentyacht/.../code/` — solo proxy, no meter contenido
- `/etc/easypanel/traefik/config/main.yaml` — gestionado por EasyPanel, no editar manualmente
- Los backups en `/home/sentyacht/backup-*` — no activar como fuente

## Qué se limpió en este cierre

- 63 archivos legacy eliminados del proyecto proxy EasyPanel (HTML, assets, JS, CSS, scripts)
- `fix-traefik-routing.sh` eliminado (obsoleto con proxy permanente)
- 3 assets huérfanos eliminados del site activo (no referenciados por páginas)

## Superficie pública

| Ruta | Contenido |
|---|---|
| GET / | Redirect -> /es/ |
| GET /es/* | Web ES (home, catálogo, fichas, legales, landing) |
| GET /en/* | Web EN (home, catálogo, fichas, legales) |
| GET /assets/* | Imágenes |
| GET /styles.css, /shared.js, /boats.* | CSS, JS, datos |
| POST /api/leads/intake/web | Unico endpoint API público |
| /api/* (resto) | 403 bloqueado |
