# Go-live checklist — Sentyacht

Fecha: 2026-03-13
Estado: no ejecutada
Prerrequisito: staging checklist completada al 100%

Ejecutar esta checklist para poner el circuito delante de tráfico real.

## 1. DNS y dominio

- [ ] Registro A de `sentyacht.com` apuntando a IP del VPS
- [ ] TTL reducido a 300s antes del cambio (para rollback rápido)
- [ ] Propagación DNS verificada: `dig sentyacht.com` devuelve la IP correcta
- [ ] HTTPS activo: `https://sentyacht.com/` carga con certificado válido (Caddy lo obtiene automáticamente al recibir el primer request con el dominio)

## 2. Rutas finales verificadas

- [ ] `https://sentyacht.com/` → web corporativa carga correctamente
- [ ] `https://sentyacht.com/vender` → landing vendedor carga correctamente
- [ ] `https://sentyacht.com/api/health` → responde OK
- [ ] `https://sentyacht.com/api/leads/webhook/landing-barcos-venta` → acepta POST

## 3. Circuito completo en dominio final

- [ ] Flujo home → contacto → CTA → landing → formulario → éxito funciona
- [ ] Lead aparece en el motor con source `webhook:landing-barcos-venta`
- [ ] Verificar en móvil real con el dominio final
- [ ] Sin errores en consola del navegador

## 4. Datos de contacto finales

- [ ] Teléfono real verificado (llamar y comprobar)
- [ ] Email real verificado (enviar correo y comprobar recepción)
- [ ] Ubicación correcta en el mapa mental del visitante

## 5. Operativa definida

- [ ] Persona responsable de revisar leads: ____________
- [ ] Frecuencia de revisión: ____________ (recomendado: diaria)
- [ ] Cómo accede a los leads: `curl https://sentyacht.com/api/leads?source=webhook:landing-barcos-venta` o interfaz futura
- [ ] Compromiso de contacto al propietario en 24-48h verificado con la persona responsable

## 6. Protección verificada en producción

- [ ] Rate limit activo y probado (enviar 10 requests rápidos → los últimos son rechazados)
- [ ] Honeypot activo y probado

## 7. Rollback

Si algo falla tras go-live:
1. Revertir DNS a la IP anterior (Arsys u otro hosting)
2. Si no hay IP anterior, apuntar DNS a un servidor con una página "en mantenimiento"
3. El TTL de 300s permite que el cambio se propague en ~5 minutos

Datos de rollback:
- IP anterior del dominio: ____________
- Registrar DNS provider: ____________ (Arsys, Hostinger, Cloudflare, etc.)

## 8. Post go-live (primeras 48h)

- [ ] Verificar que Caddy renovó/obtuvo el certificado correctamente
- [ ] Verificar que uvicorn sigue activo (`systemctl status openclaw`)
- [ ] Verificar que el backup diario se ejecutó
- [ ] Revisar si han llegado leads reales o solo spam
- [ ] Si llegan leads: contactar al primero y evaluar calidad del circuito
- [ ] Si no llegan leads en 48h: verificar que el formulario funciona, no asumir problema de conversión
