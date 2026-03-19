# Runbook: Gestión de barcos y galerías

## Arquitectura

```
data/boats/{slug}.json        ← FUENTE DE VERDAD (texto, specs, precios)
assets/boats/{slug}/manifest.json  ← ORDEN DE GALERÍA (imágenes)
              ↓
    scripts/build_site.py     ← GENERADOR
              ↓
    boats.js (GENERADO)       ← NO editar manualmente
    es/barcos/{slug}/         ← NO editar manualmente
    en/boats/{slug}/          ← NO editar manualmente
```

## Archivos generados (NO editar)

Estos archivos se regeneran con cada build. Los cambios manuales se perderán:
- `static/site/boats.js`
- `static/site/es/barcos/*/index.html`
- `static/site/en/boats/*/index.html`

## Flujo principal: usar el admin

1. Abrir `/internal/admin/` en el navegador
2. Introducir la API key
3. Click en un barco → Tab "Texto" para editar datos, Tab "Imágenes" para reordenar
4. "Guardar y publicar" regenera todo el sitio
5. Desplegar con `bash deploy/deploy-staging.sh`

## Flujo CLI (alternativo)

Si prefieres editar directamente:

1. Edita `static/site/data/boats/{slug}.json`
2. Ejecuta `python scripts/build_site.py`
3. Despliega

## Reordenar fotos

**Desde el admin:**
1. Click en barco → Tab "Imágenes"
2. Arrastra para reordenar (primera = hero)
3. "Guardar y regenerar"

**Desde CLI:**
1. Edita `static/site/assets/boats/{slug}/manifest.json` → array `files`
2. Ejecuta `python scripts/build_site.py`

## Añadir fotos a un barco

1. Coloca los JPGs en `static/site/assets/boats/{slug}/`
2. Añade los nombres al array `files` en `manifest.json`
3. Ejecuta `python scripts/build_site.py` o usa "Guardar y regenerar" en el admin

## Crear un barco nuevo

**Desde el admin:**
1. "+ Nuevo barco" → nombre + slug → "Crear barco"
2. Se crea como borrador (no visible)
3. Coloca JPGs en la carpeta de assets
4. Edita texto + reordena galería desde el admin
5. "Publicar" cuando esté listo

**Desde CLI:**
1. Crea `static/site/data/boats/{slug}.json` con el esquema completo
2. Crea `static/site/assets/boats/{slug}/` con manifest.json y JPGs
3. Ejecuta `python scripts/build_site.py`

## Publicar / Ocultar un barco

- Campo `visible` en `data/boats/{slug}.json`: `true` = publicado, `false` = borrador
- Desde el admin: botón "Publicar" / "Ocultar"
- Los borradores no aparecen en listados públicos pero sí en el admin

## Validación

`build_site.py` valida antes de escribir:

| Validación | Qué comprueba |
|---|---|
| JSON válido | Cada data JSON es parseable |
| Slug coherente | slug en JSON coincide con nombre del archivo |
| Campos requeridos | name, brand, type, year, price, length, location |
| Manifest files | Nombres seguros, sin duplicados, existen en disco |

Si **cualquier** archivo falla validación, el build aborta sin escribir nada.

## Scripts

| Script | Estado | Función |
|---|---|---|
| `scripts/build_site.py` | **Activo** | Genera boats.js + 24 páginas HTML |
| `scripts/integrate_galleries.py` | Deprecated | Wrapper que delega a build_site.py |
| `scripts/migrate_boats_to_json.py` | One-time | Migración inicial de boats.js a JSONs |

## Errores comunes

| Error | Causa | Solución |
|---|---|---|
| `missing required field` | JSON de barco incompleto | Rellenar el campo en data/boats/{slug}.json |
| `slug doesn't match filename` | slug en JSON distinto al nombre del archivo | Corregir el slug o el nombre del archivo |
| Build produce páginas sin galería | manifest.json tiene `files: []` | Añadir imágenes al manifest |
| Barco no aparece en listados | `visible: false` o falta en el JSON | Cambiar visible a true y rebuild |
