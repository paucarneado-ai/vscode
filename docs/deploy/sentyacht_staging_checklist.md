# Staging checklist — Sentyacht en Hostinger VPS

Fecha: 2026-03-13
Estado: no ejecutada

Ejecutar esta checklist ANTES de mover el dominio. Todo se prueba accediendo por IP directa del VPS o con `/etc/hosts` apuntando el dominio a la IP del VPS.

## 1. Servidor base

- [ ] VPS contratado en Hostinger (Ubuntu 22.04+ o Debian 12+)
- [ ] Acceso SSH con clave (no solo contraseña)
- [ ] Firewall configurado: puertos 22, 80, 443 abiertos
- [ ] Python 3.11+ instalado
- [ ] Caddy instalado (paquete oficial o binario)

## 2. Código y dependencias

- [ ] Repo clonado en `/home/openclaw/`
- [ ] `pip install -r requirements.txt` en virtualenv
- [ ] Directorio `/home/openclaw/data/` creado con permisos de escritura
- [ ] Archivo `.env` configurado con variables necesarias

## 3. API funcionando

- [ ] uvicorn arranca sin errores: `uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --workers 1`
- [ ] `curl http://127.0.0.1:8000/health` responde OK
- [ ] `curl -X POST http://127.0.0.1:8000/leads/webhook/staging-test -H "Content-Type: application/json" -d '{"name":"Test","email":"test@staging.com","notes":"staging"}'` responde 200
- [ ] `curl http://127.0.0.1:8000/leads?source=webhook:staging-test` devuelve el lead creado
- [ ] Servicio systemd `openclaw.service` creado y activo (`systemctl status openclaw`)
- [ ] API se reinicia automáticamente tras `kill` del proceso

## 4. Reverse proxy y estáticos

- [ ] Caddyfile configurado según plan de despliegue
- [ ] Caddy arranca sin errores (`systemctl status caddy`)
- [ ] `http://<IP-VPS>/` carga la web corporativa (index.html)
- [ ] `http://<IP-VPS>/vender` carga la landing de vendedor
- [ ] `http://<IP-VPS>/api/health` responde OK
- [ ] CSS y estilos cargan correctamente (no broken styles)

## 5. Circuito completo (staging)

- [ ] Abrir home en navegador → navegar a contacto → clic en CTA → llega a /vender
- [ ] Rellenar formulario con datos de prueba → enviar → pantalla de éxito
- [ ] Verificar que el lead aparece en el motor: `curl http://<IP-VPS>/api/leads?source=webhook:landing-barcos-venta`
- [ ] Enviar mismo email dos veces → verificar que muestra éxito (duplicado manejado)
- [ ] Probar en móvil real: home + landing + formulario + menú hamburguesa

## 6. Landing API_BASE

- [ ] Landing desplegada está en `static/site/vender/index.html` (la versión con `API_BASE = "/api"`)
- [ ] Formulario envía a `/api/leads/webhook/landing-barcos-venta` correctamente
- [ ] Sin errores de CORS en consola del navegador
- [ ] Verificar que no existe `static/landing-barcos-venta.html` (eliminado — fuente única en `site/vender/index.html`)

## 7. Datos reales (antes de go-live)

- [ ] Teléfono placeholder sustituido por número real en `index.html`
- [ ] Email placeholder sustituido por email real en `index.html`
- [ ] Buzón de email verificado (recibe correo)
- [ ] Apellido de Jordi añadido (si confirmado) o texto reformulado

## 8. Protección mínima (antes de go-live)

- [ ] Honeypot verificado: abrir DevTools → rellenar campo oculto `website` → enviar → debe mostrar éxito SIN crear lead en backend
- [ ] Honeypot verificado: enviar formulario normal (sin rellenar `website`) → lead SÍ debe aparecer en backend
- [ ] Rate limiting: evaluar si se instala módulo `caddy-ratelimit` o se usa iptables/fail2ban como alternativa
- [ ] Si rate limiting activo: enviar 10 requests rápidos al webhook → los últimos deben ser rechazados

## 9. Backup

- [ ] Cron de backup diario de SQLite configurado
- [ ] Verificado que el backup se crea correctamente
- [ ] Al menos un backup manual guardado antes de go-live
