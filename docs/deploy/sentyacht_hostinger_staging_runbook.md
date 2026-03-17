# Staging runbook — Sentyacht en Hostinger VPS

Fecha: 2026-03-13
Estado: listo para ejecutar
Capa: bridging layer

Este runbook levanta el circuito vendedor completo en un VPS para validación end-to-end **antes de mover el dominio**. Todo se accede por IP directa.

---

## 1. Prerequisitos del VPS

**Requisitos:**
- Ubuntu 22.04+ o Debian 12+ con acceso root/sudo
- Acceso SSH con clave
- Puertos 22, 80, 443 abiertos en firewall
- Mínimo 1 GB RAM, 10 GB disco

**Software a instalar:**

```bash
# Python 3.11+
sudo apt update && sudo apt install -y python3 python3-venv python3-pip

# Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy

# SQLite (normalmente ya incluido)
sudo apt install -y sqlite3
```

## 2. Crear usuarios y estructura

```bash
# Usuario para el backend (core reusable)
sudo useradd -m -s /bin/bash openclaw

# Usuario para la web estática (vertical-specific)
sudo useradd -m -s /bin/bash sentyacht

# Directorios openclaw
sudo -u openclaw mkdir -p /home/openclaw/{app,data,backups,deploy}

# Directorio sentyacht
sudo -u sentyacht mkdir -p /home/sentyacht/site

# Crear virtualenv
sudo -u openclaw python3 -m venv /home/openclaw/venv
```

## 3. Copiar archivos del repo al VPS

Desde la máquina local (ajustar IP). Ejecutar desde WSL o Git Bash (rsync no está disponible en PowerShell/CMD nativo de Windows).

```bash
VPS_IP="x.x.x.x"

# 3a. Backend (core reusable) → /home/openclaw/app/
rsync -avz --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' \
  --exclude 'data/' --exclude '.env' --exclude 'static/' \
  --exclude 'tests/' --exclude 'docs/' --exclude 'scripts/' \
  ./apps/ root@${VPS_IP}:/home/openclaw/app/apps/
rsync -avz ./requirements.txt root@${VPS_IP}:/home/openclaw/app/

# 3b. Web estática (vertical-specific) → /home/sentyacht/site/
rsync -avz ./static/site/ root@${VPS_IP}:/home/sentyacht/site/

# 3c. Configs de despliegue → /home/openclaw/deploy/
rsync -avz ./deploy/ root@${VPS_IP}:/home/openclaw/deploy/

# 3d. Fijar permisos
# Caddy corre como usuario 'caddy' y necesita leer /home/sentyacht/site/
ssh root@${VPS_IP} 'chown -R openclaw:openclaw /home/openclaw/ && chown -R sentyacht:sentyacht /home/sentyacht/ && chmod 755 /home/sentyacht /home/sentyacht/site'

# Alternativa sin rsync (Windows nativo con OpenSSH):
# scp -r ./apps/ root@${VPS_IP}:/home/openclaw/app/apps/
# scp ./requirements.txt root@${VPS_IP}:/home/openclaw/app/
# scp -r ./static/site/ root@${VPS_IP}:/home/sentyacht/site/
# scp -r ./deploy/ root@${VPS_IP}:/home/openclaw/deploy/
# ssh root@${VPS_IP} 'chown -R openclaw:openclaw /home/openclaw/ && chown -R sentyacht:sentyacht /home/sentyacht/ && chmod 755 /home/sentyacht /home/sentyacht/site'
```

## 4. Instalar dependencias Python

```bash
sudo -u openclaw /home/openclaw/venv/bin/pip install -r /home/openclaw/app/requirements.txt
```

## 5. Crear archivo .env

```bash
sudo -u openclaw nano /home/openclaw/.env
```

Contenido mínimo (ajustar según el proyecto):
```
# OpenClaw environment
DATABASE_PATH=/home/openclaw/data/leads.db
```

## 6. Verificar API manualmente

```bash
# Arrancar uvicorn directamente para comprobar que funciona
# Desde /home/openclaw/app (mismo WorkingDirectory que systemd)
cd /home/openclaw/app
sudo -u openclaw DATABASE_PATH=/home/openclaw/data/leads.db \
  /home/openclaw/venv/bin/uvicorn apps.api.main:app \
  --host 127.0.0.1 --port 8000 --workers 1

# En otra terminal SSH:
curl http://127.0.0.1:8000/health
# Esperado: respuesta OK

curl -X POST http://127.0.0.1:8000/leads/webhook/staging-test \
  -H "Content-Type: application/json" \
  -d '{"name":"Staging Test","email":"staging@test.com","notes":"Teléfono: +34600000000\nTipo: Velero\nEslora: 12m"}'
# Esperado: 200 con lead creado

curl "http://127.0.0.1:8000/leads?source=webhook:staging-test"
# Esperado: array con el lead creado

# Parar uvicorn manual (Ctrl+C)
```

## 7. Configurar systemd para la API

```bash
# Copiar unit file
sudo cp /home/openclaw/deploy/systemd/openclaw-api.service /etc/systemd/system/

# Activar y arrancar
sudo systemctl daemon-reload
sudo systemctl enable openclaw-api
sudo systemctl start openclaw-api

# Verificar
sudo systemctl status openclaw-api
curl http://127.0.0.1:8000/health
```

## 8. Configurar Caddy para staging

Para staging (sin dominio), usar la IP directa. Caddy no intentará HTTPS con una IP.

```bash
# Hacer backup del Caddyfile original
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.backup

# Crear Caddyfile de staging (con IP en vez de dominio)
sudo tee /etc/caddy/Caddyfile > /dev/null <<'EOF'
:80 {
    handle /api/* {
        uri strip_prefix /api
        reverse_proxy localhost:8000
    }

    handle {
        file_server {
            root /home/sentyacht/site
        }
    }
}
EOF

# Recargar Caddy
sudo systemctl reload caddy
sudo systemctl status caddy
```

## 9. Verificar rutas estáticas

Desde cualquier navegador o curl (reemplazar IP):

```bash
VPS_IP="x.x.x.x"

# Home corporativa
curl -s http://${VPS_IP}/ | head -5
# Esperado: <!DOCTYPE html> con título Sentyacht

# Landing vendedor
curl -s http://${VPS_IP}/vender/ | head -5
# Esperado: <!DOCTYPE html> con título "Venta profesional de embarcaciones"

# CSS
curl -s -o /dev/null -w "%{http_code}" http://${VPS_IP}/css/brand.css
# Esperado: 200

# API a través de Caddy
curl http://${VPS_IP}/api/health
# Esperado: respuesta OK
```

## 10. Verificar circuito completo

### 10.1 Flujo manual en navegador

1. Abrir `http://<VPS_IP>/` en navegador
2. Navegar hasta sección "Contacto"
3. Clic en "Solicitar valoración y asesoramiento"
4. Verificar que llega a `http://<VPS_IP>/vender/`
5. Rellenar formulario con datos de prueba
6. Enviar → debe mostrar "Solicitud recibida"
7. Verificar lead en backend:

```bash
curl "http://${VPS_IP}/api/leads?source=webhook:landing-barcos-venta"
```

### 10.2 Verificar honeypot

1. Abrir `http://<VPS_IP>/vender/` en navegador
2. Abrir DevTools → Console
3. Ejecutar: `document.getElementById('website').value = 'spam'`
4. Rellenar resto del formulario y enviar
5. Debe mostrar "Solicitud recibida" pero NO debe crear lead en backend:

```bash
# Contar leads — no debe haber aumentado
curl "http://${VPS_IP}/api/leads?source=webhook:landing-barcos-venta" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))"
```

### 10.3 Verificar duplicados

1. Enviar formulario con el mismo email dos veces
2. Ambos envíos deben mostrar "Solicitud recibida"
3. Solo debe existir un lead con ese email:

```bash
curl "http://${VPS_IP}/api/leads?q=<email-usado>"
```

### 10.4 Verificar móvil

- Abrir `http://<VPS_IP>/` en móvil real
- Verificar menú hamburguesa funciona
- Navegar a landing, rellenar formulario
- Verificar que inputs no hacen zoom raro (font-size >= 16px)

## 11. Verificar revisión operativa

```bash
# Listar todos los leads de la landing
curl "http://${VPS_IP}/api/leads?source=webhook:landing-barcos-venta"

# Ver lead pack de un lead específico (reemplazar ID)
curl "http://${VPS_IP}/api/leads/1/pack"

# Ver delivery
curl "http://${VPS_IP}/api/leads/1/delivery"
```

## 12. Backup manual antes de go-live

```bash
sudo -u openclaw sqlite3 /home/openclaw/data/leads.db \
  ".backup /home/openclaw/backups/leads_staging_$(date +%Y%m%d_%H%M%S).db"

# Verificar
ls -la /home/openclaw/backups/
```

## 13. Rollback simple

Si algo falla en staging:

```bash
# Parar servicios
sudo systemctl stop openclaw-api
sudo systemctl stop caddy

# Restaurar Caddyfile original
sudo cp /etc/caddy/Caddyfile.backup /etc/caddy/Caddyfile
sudo systemctl start caddy

# La API se puede volver a arrancar en cualquier momento
sudo systemctl start openclaw-api
```

## 14. Qué NO hacer todavía

- **No mover DNS** — staging se valida por IP. El dominio se apunta solo tras completar la go-live checklist.
- **No compartir la URL de staging** con propietarios reales — los leads de staging son de prueba.
- **No instalar rate limiting** todavía — evaluar en staging si se necesita `xcaddy` o basta con iptables.
- **No sustituir placeholders** (teléfono, email, apellido) hasta que se confirmen los datos reales.
- **No configurar HTTPS** — Caddy lo hará automáticamente cuando el dominio apunte a la IP y se use el Caddyfile de producción.
- **No eliminar leads de staging** de la base de datos — se pueden limpiar antes de go-live con `DELETE FROM leads WHERE source = 'webhook:staging-test'`.

## 15. Transición staging → producción

Cuando staging esté validado:

1. Sustituir placeholders (teléfono, email, apellido Jordi) en `/home/sentyacht/site/index.html`
2. Copiar `deploy/Caddyfile.sentyacht` a `/etc/caddy/Caddyfile` (con dominio real en vez de `:80`)
3. Apuntar DNS (registro A de sentyacht.com → IP del VPS)
4. `sudo systemctl reload caddy` — Caddy obtendrá certificado HTTPS automáticamente
5. Ejecutar go-live checklist completa (`docs/deploy/sentyacht_go_live_checklist.md`)
6. Limpiar leads de staging: `sqlite3 /home/openclaw/data/leads.db "DELETE FROM leads WHERE source = 'webhook:staging-test'"`
