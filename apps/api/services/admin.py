"""Admin service — boat and gallery management via JSON data files."""

import json
import os
import re
import subprocess
import sys

SITE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "site"))
DATA_DIR = os.path.join(SITE_DIR, "data", "boats")
BOATS_DIR = os.path.join(SITE_DIR, "assets", "boats")
SCRIPTS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts"))

SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9_\-]+\.jpg$")


# ═══════════════════════════════════════════════════════════════════
# Boat listing (reads from data JSONs + manifests)
# ═══════════════════════════════════════════════════════════════════

def list_boats() -> list[dict]:
    """List all boats from data JSON files, enriched with gallery info."""
    boats = []
    if not os.path.isdir(DATA_DIR):
        return boats
    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(DATA_DIR, fname)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        slug = data.get("slug", fname[:-5])
        # Gallery info from manifest
        manifest_files = _load_manifest_files(slug)
        boats.append({
            "slug": slug,
            "name": data.get("name", slug),
            "visible": data.get("visible", True),
            "brand": data.get("brand", ""),
            "year": data.get("year", 0),
            "price": data.get("price", 0),
            "image_count": len(manifest_files),
            "hero": manifest_files[0] if manifest_files else None,
        })
    return boats


def get_boat(slug: str) -> dict | None:
    """Get boat summary for admin edit view (data + gallery info)."""
    if not SAFE_SLUG.match(slug):
        return None
    data = _read_boat_data(slug)
    if data is None:
        return None
    manifest_files = _load_manifest_files(slug)
    return {
        "slug": slug,
        "name": data.get("name", slug),
        "visible": data.get("visible", True),
        "files": manifest_files,
        "directory": f"static/site/assets/boats/{slug}/",
    }


# ═══════════════════════════════════════════════════════════════════
# Boat data CRUD (reads/writes data/boats/{slug}.json)
# ═══════════════════════════════════════════════════════════════════

def get_boat_data(slug: str) -> dict | None:
    """Read full boat data JSON for editing."""
    if not SAFE_SLUG.match(slug):
        return None
    return _read_boat_data(slug)


def update_boat_data(slug: str, data: dict) -> tuple[bool, str]:
    """Validate and write updated boat data."""
    if not SAFE_SLUG.match(slug):
        return False, "slug inválido"
    if data.get("slug") and data["slug"] != slug:
        return False, "no se puede cambiar el slug"

    data_path = os.path.join(DATA_DIR, f"{slug}.json")
    if not os.path.isfile(data_path):
        return False, "barco no encontrado"

    # Ensure slug is set
    data["slug"] = slug

    # Basic validation
    for field in ("name", "brand"):
        if not data.get(field, "").strip():
            return False, f"campo '{field}' no puede estar vacío"

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return True, "datos guardados"


def set_boat_visibility(slug: str, visible: bool) -> tuple[bool, str]:
    """Toggle boat visibility and run build."""
    data = _read_boat_data(slug)
    if data is None:
        return False, "barco no encontrado"
    data["visible"] = visible
    data_path = os.path.join(DATA_DIR, f"{slug}.json")
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    ok, output = run_build()
    status = "publicado" if visible else "ocultado"
    if ok:
        return True, f"barco {status} y sitio regenerado"
    return False, f"barco {status} pero error regenerando: {output}"


# ═══════════════════════════════════════════════════════════════════
# Gallery management (reads/writes manifest.json)
# ═══════════════════════════════════════════════════════════════════

def update_gallery_order(slug: str, files: list[str]) -> tuple[bool, str]:
    """Rewrite the files array in a boat's manifest.json."""
    if not SAFE_SLUG.match(slug):
        return False, "slug inválido"
    manifest_path = os.path.join(BOATS_DIR, slug, "manifest.json")
    if not os.path.isfile(manifest_path):
        return False, "barco no encontrado"

    if not files:
        return False, "la lista de archivos no puede estar vacía"

    for f in files:
        if not SAFE_FILENAME.match(f):
            return False, f"nombre de archivo no válido: {f}"

    if len(files) != len(set(files)):
        return False, "hay archivos duplicados en la lista"

    boat_dir = os.path.join(BOATS_DIR, slug)
    missing = [f for f in files if not os.path.isfile(os.path.join(boat_dir, f))]
    if missing:
        return False, f"archivos no encontrados en disco: {missing}"

    try:
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return False, f"error leyendo manifest: {e}"

    data["files"] = files
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return True, "orden de galería actualizado"


# ═══════════════════════════════════════════════════════════════════
# Create boat
# ═══════════════════════════════════════════════════════════════════

def create_boat(slug: str, name: str) -> tuple[bool, str]:
    """Create a new boat: data JSON + asset directory + manifest, then build."""
    if not SAFE_SLUG.match(slug):
        return False, "slug inválido (solo minúsculas, números y guiones)"
    if not name or not name.strip():
        return False, "el nombre no puede estar vacío"
    name = name.strip()

    data_path = os.path.join(DATA_DIR, f"{slug}.json")
    if os.path.isfile(data_path):
        return False, f"ya existe el barco '{slug}'"

    # 1. Create data JSON
    os.makedirs(DATA_DIR, exist_ok=True)
    boat_data = {
        "slug": slug,
        "name": name,
        "visible": False,
        "brand": "PENDIENTE",
        "type": "motor",
        "year": 0,
        "price": 0,
        "length": 0,
        "beam": 0,
        "draft": 0,
        "location": "PENDIENTE",
        "condition": "used",
        "badges": [],
        "engines": "PENDIENTE",
        "fuel": "PENDIENTE",
        "cabins": 0,
        "berths": 0,
        "heads": 0,
        "description": {
            "es": "Pendiente de completar.",
            "en": "Pending completion.",
        },
        "specs": {"es": {}, "en": {}},
        "images": [],
    }
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(boat_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # 2. Create asset directory + manifest
    boat_dir = os.path.join(BOATS_DIR, slug)
    os.makedirs(boat_dir, exist_ok=True)
    manifest = {"slug": slug, "name": name, "status": "PENDING", "files": []}
    with open(os.path.join(boat_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # 3. Run build to generate boats.js + placeholder HTML pages
    ok, output = run_build()
    if not ok:
        return True, f"barco creado pero error en build: {output}"

    return True, "barco creado y sitio regenerado"


# ═══════════════════════════════════════════════════════════════════
# Build
# ═══════════════════════════════════════════════════════════════════

def run_build() -> tuple[bool, str]:
    """Run build_site.py to regenerate boats.js + all HTML pages."""
    script = os.path.join(SCRIPTS_DIR, "build_site.py")
    if not os.path.isfile(script):
        return False, "script build_site.py no encontrado"
    try:
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout ejecutando build_site.py"
    output = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode == 0, output


def regenerate_galleries() -> tuple[bool, str]:
    """Backwards-compatible alias for run_build()."""
    return run_build()


# ═══════════════════════════════════════════════════════════════════
# Image serving
# ═══════════════════════════════════════════════════════════════════

def get_image_path(slug: str, filename: str) -> str | None:
    """Return validated absolute path to a boat image, or None."""
    if not SAFE_SLUG.match(slug):
        return None
    if not SAFE_FILENAME.match(filename):
        return None
    path = os.path.join(BOATS_DIR, slug, filename)
    real_path = os.path.realpath(path)
    real_boats = os.path.realpath(BOATS_DIR)
    if not real_path.startswith(real_boats):
        return None
    if not os.path.isfile(real_path):
        return None
    return real_path


# ═══════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════

def _read_boat_data(slug: str) -> dict | None:
    """Read a boat's data JSON file."""
    data_path = os.path.join(DATA_DIR, f"{slug}.json")
    if not os.path.isfile(data_path):
        return None
    try:
        with open(data_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _load_manifest_files(slug: str) -> list[str]:
    """Load gallery file list from manifest.json."""
    manifest_path = os.path.join(BOATS_DIR, slug, "manifest.json")
    if not os.path.isfile(manifest_path):
        return []
    try:
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
        files = data.get("files", [])
        return files if isinstance(files, list) else []
    except (json.JSONDecodeError, OSError):
        return []
