"""Build static site from boat JSON data files.

Reads per-boat JSON files from static/site/data/boats/ and gallery manifests
from static/site/assets/boats/, then generates:
  1. static/site/boats.js  (catalog data + helper functions)
  2. static/site/es/barcos/{slug}/index.html  (12 detail pages)
  3. static/site/en/boats/{slug}/index.html   (12 detail pages)

Usage: python scripts/build_site.py
"""

import json
import os
import re
import sys
import urllib.parse

SITE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "static", "site"))
DATA_DIR = os.path.join(SITE_DIR, "data", "boats")
ASSETS_DIR = os.path.join(SITE_DIR, "assets", "boats")

SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9_\-]+\.jpg$")


# ═══════════════════════════════════════════════════════════════════
# Loading & Validation
# ═══════════════════════════════════════════════════════════════════

def load_all_boats() -> list[dict]:
    """Load all boat JSON files, validate, return sorted by slug."""
    boats = []
    errors = []
    if not os.path.isdir(DATA_DIR):
        print(f"ERROR: data directory not found: {DATA_DIR}")
        sys.exit(1)

    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(DATA_DIR, fname)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            errors.append(f"{fname}: {e}")
            continue

        slug = data.get("slug", "")
        expected_slug = fname[:-5]  # strip .json
        if slug != expected_slug:
            errors.append(f"{fname}: slug '{slug}' doesn't match filename")
            continue

        # Required fields check
        for field in ("name", "brand", "type", "year", "price", "length", "location"):
            if field not in data:
                errors.append(f"{fname}: missing required field '{field}'")

        boats.append(data)

    if errors:
        for e in errors:
            print(f"  ERROR: {e}")
        print(f"\n{len(errors)} validation error(s). Aborting build.")
        sys.exit(1)

    return boats


def load_manifest(slug: str) -> list[str]:
    """Load gallery files from a boat's manifest.json."""
    manifest_path = os.path.join(ASSETS_DIR, slug, "manifest.json")
    if not os.path.isfile(manifest_path):
        return []
    try:
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
        files = data.get("files", [])
        if not isinstance(files, list):
            return []
        return [f for f in files if SAFE_FILENAME.match(f)]
    except (json.JSONDecodeError, OSError):
        return []


# ═══════════════════════════════════════════════════════════════════
# Price formatting
# ═══════════════════════════════════════════════════════════════════

def format_price_es(price: int) -> str:
    """129000 -> '129.000 €'"""
    s = f"{price:,}".replace(",", ".")
    return f"{s} €"


def format_price_en(price: int) -> str:
    """129000 -> '€129,000'"""
    s = f"{price:,}"
    return f"€{s}"


# ═══════════════════════════════════════════════════════════════════
# Similar boats
# ═══════════════════════════════════════════════════════════════════

def compute_similar_boats(boat: dict, all_boats: list[dict], count: int = 3) -> list[dict]:
    """Port of getSimilarBoats() JS logic."""
    slug = boat["slug"]
    candidates = [b for b in all_boats if b["slug"] != slug and b.get("visible") is not False]

    def score(b):
        type_match = 2 if b.get("type") == boat.get("type") else 0
        price_proximity = 1 / (1 + abs(b.get("price", 0) - boat.get("price", 0)) / 100000)
        return type_match + price_proximity

    candidates.sort(key=score, reverse=True)
    return candidates[:count]


# ═══════════════════════════════════════════════════════════════════
# boats.js generation
# ═══════════════════════════════════════════════════════════════════

def _js_value(val, indent=4) -> str:
    """Convert a Python value to JS literal syntax."""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        # Format floats without trailing zeros for clean output
        if isinstance(val, float):
            s = f"{val:.2f}".rstrip("0").rstrip(".")
            # But keep at least one decimal if it was a float like 5.90
            if "." not in s:
                return s
            return s
        return str(val)
    if isinstance(val, str):
        # Escape for JS string
        escaped = val.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    if isinstance(val, list):
        if not val:
            return "[]"
        items = ", ".join(_js_value(v) for v in val)
        return f"[{items}]"
    if isinstance(val, dict):
        if not val:
            return "{}"
        pad = " " * indent
        inner_pad = " " * (indent + 2)
        lines = []
        for k, v in val.items():
            lines.append(f'{inner_pad}"{k}": {_js_value(v, indent + 2)}')
        return "{\n" + ",\n".join(lines) + f"\n{pad}}}"
    return str(val)


# Field order matching current boats.js
BOAT_JS_FIELDS = [
    "slug", "name", "visible", "brand", "type", "year", "price",
    "length", "beam", "draft", "location", "condition", "badges",
    "engines", "fuel", "cabins", "berths", "heads",
    "description", "specs", "images",
]

HELPERS_JS = r"""
/* ─── Helper Functions ─── */

/** Get only published boats (visible !== false) */
function getPublishedBoats() {
  return boats.filter(b => b.visible !== false);
}

/** Format price with European locale: 1.300.000 € */
function formatPrice(price) {
  return price.toLocaleString('es-ES') + ' €';
}

/** Get boats filtered by criteria */
function filterBoats(filters = {}) {
  return boats.filter(boat => {
    if (boat.visible === false) return false;
    if (filters.type && boat.type !== filters.type) return false;
    if (filters.brand && boat.brand !== filters.brand) return false;
    if (filters.location && boat.location !== filters.location) return false;
    if (filters.minPrice && boat.price < filters.minPrice) return false;
    if (filters.maxPrice && boat.price > filters.maxPrice) return false;
    if (filters.minLength && boat.length < filters.minLength) return false;
    if (filters.maxLength && boat.length > filters.maxLength) return false;
    if (filters.minYear && boat.year < filters.minYear) return false;
    if (filters.maxYear && boat.year > filters.maxYear) return false;
    if (filters.search) {
      const q = filters.search.toLowerCase();
      const searchable = `${boat.name} ${boat.brand} ${boat.location}`.toLowerCase();
      if (!searchable.includes(q)) return false;
    }
    return true;
  });
}

/** Get unique values for filter options */
function getFilterOptions() {
  return {
    brands: [...new Set(boats.map(b => b.brand))].sort(),
    locations: [...new Set(boats.map(b => b.location))].sort(),
    types: [...new Set(boats.map(b => b.type))],
    priceRange: { min: Math.min(...boats.map(b => b.price)), max: Math.max(...boats.map(b => b.price)) },
    lengthRange: { min: Math.min(...boats.map(b => b.length)), max: Math.max(...boats.map(b => b.length)) },
    yearRange: { min: Math.min(...boats.map(b => b.year)), max: Math.max(...boats.map(b => b.year)) }
  };
}

/** Get a boat by slug */
function getBoatBySlug(slug) {
  return boats.find(b => b.slug === slug) || null;
}

/** Get similar boats (same type or similar price, excluding current) */
function getSimilarBoats(slug, count = 3) {
  const current = getBoatBySlug(slug);
  if (!current) return [];
  return boats
    .filter(b => b.slug !== slug)
    .sort((a, b) => {
      const aScore = (a.type === current.type ? 2 : 0) + (1 / (1 + Math.abs(a.price - current.price) / 100000));
      const bScore = (b.type === current.type ? 2 : 0) + (1 / (1 + Math.abs(b.price - current.price) / 100000));
      return bScore - aScore;
    })
    .slice(0, count);
}

/** Sort boats by field */
function sortBoats(boatList, field, direction = 'desc') {
  return [...boatList].sort((a, b) => {
    const va = a[field], vb = b[field];
    return direction === 'asc' ? va - vb : vb - va;
  });
}
"""


def build_boats_js(boats: list[dict]) -> str:
    """Generate complete boats.js content."""
    lines = [
        "/**",
        " * SentYacht — Boat Inventory Data",
        " * GENERATED by scripts/build_site.py — do not edit manually.",
        " * Source of truth: static/site/data/boats/*.json",
        " *",
        " * NOTE on images:",
        " * - `images` here = listing card thumbnail only (flat path: /assets/{file}).",
        " *   Used by catalog pages (home, yates-en-venta, yachts-for-sale).",
        " * - Gallery order for detail pages lives in manifest.json per boat:",
        " *   static/site/assets/boats/{slug}/manifest.json → files[]",
        " *   Managed via tools/admin.html + scripts/build_site.py",
        " */",
        "const boats = [",
    ]

    for i, boat in enumerate(boats):
        lines.append("  {")
        fields_written = []
        for field in BOAT_JS_FIELDS:
            if field not in boat:
                continue
            val = boat[field]
            # Skip visible if true (backwards compat: absent = visible)
            if field == "visible" and val is True:
                continue
            js_val = _js_value(val, indent=4)
            fields_written.append(f"    {field}: {js_val}")
        lines.append(",\n".join(fields_written))
        comma = "," if i < len(boats) - 1 else ""
        lines.append(f"  }}{comma}")

    lines.append("];")
    lines.append(HELPERS_JS)

    return "\n".join(lines) + "\n"


# ═══════════════════════════════════════════════════════════════════
# Gallery HTML (ported from integrate_galleries.py)
# ═══════════════════════════════════════════════════════════════════

def build_gallery_html(slug: str, alt_name: str, files: list[str]) -> str:
    """Build gallery HTML from manifest files list."""
    if not files:
        return '      <!-- Gallery -->\n      <div class="aspect-[16/9] bg-dark-base rounded-sm flex items-center justify-center">\n        <p class="text-txt-dark-2/40 text-sm">Fotos pendientes</p>\n      </div>'

    hero = files[0]
    thumbs = files[1:]
    base_path = f"/assets/boats/{slug}"

    lines = ["      <!-- Gallery -->"]
    lines.append(f'      <a href="{base_path}/{hero}" class="glightbox block aspect-[16/9] overflow-hidden rounded-sm" data-gallery="boat">')
    lines.append(f'        <img src="{base_path}/{hero}" alt="{alt_name}" class="w-full h-full object-cover" style="transition: transform 0.6s cubic-bezier(0.16,1,0.3,1);" onmouseover="this.style.transform=\'scale(1.03)\'" onmouseout="this.style.transform=\'scale(1)\'">')
    lines.append("      </a>")

    if thumbs:
        lines.append('      <div class="grid grid-cols-4 sm:grid-cols-6 gap-2 mt-3">')
        for i, thumb in enumerate(thumbs):
            lazy = ' loading="lazy"' if i >= 4 else ""
            lines.append(f'        <a href="{base_path}/{thumb}" class="glightbox aspect-[4/3] overflow-hidden rounded-sm" data-gallery="boat"><img src="{base_path}/{thumb}" alt="{alt_name}" class="w-full h-full object-cover hover:opacity-80" style="transition:opacity 0.3s;"{lazy}></a>')
        lines.append("      </div>")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Detail page HTML generation
# ═══════════════════════════════════════════════════════════════════

# Badge labels per language
BADGE_LABELS = {
    "es": {"stock": "En stock", "new": "Novedad", "price-drop": "Precio rebajado"},
    "en": {"stock": "In Stock", "new": "New", "price-drop": "Price Drop"},
}
BADGE_CSS = {"stock": "badge-stock", "new": "badge-new", "price-drop": "badge-price-drop"}

TYPE_LABELS = {"es": {"motor": "Motor", "sail": "Velero"}, "en": {"motor": "Motor", "sail": "Sail"}}


def build_detail_page(boat: dict, lang: str, gallery_files: list[str], all_boats: list[dict]) -> str:
    """Generate a complete detail HTML page."""
    is_es = lang == "es"
    slug = boat["slug"]
    name = boat["name"]
    brand = boat["brand"]
    year = boat["year"]
    price = boat.get("price", 0)
    length = boat.get("length", 0)
    location = boat.get("location", "")
    engines = boat.get("engines", "")
    boat_type = boat.get("type", "motor")
    description = boat.get("description", {}).get(lang, "")
    specs = boat.get("specs", {}).get(lang, {})
    badges = boat.get("badges", [])
    images = boat.get("images", [])

    # Paths
    alt_lang = "en" if is_es else "es"
    own_path = f"/es/barcos/{slug}/" if is_es else f"/en/boats/{slug}/"
    alt_path = f"/en/boats/{slug}/" if is_es else f"/es/barcos/{slug}/"
    home = f"/{lang}/"
    catalog = "/es/yates-en-venta/" if is_es else "/en/yachts-for-sale/"

    # Price strings
    price_body = format_price_es(price) if price else "— €"
    price_title = format_price_es(price) if is_es else format_price_en(price)
    if not price:
        price_title = "— €"

    # Meta description
    length_str = f"{length}m" if length else ""
    if is_es:
        meta_desc = f"{name} ({year}) en venta. {length_str}, {engines}. Precio: {format_price_es(price)}. Visita en {location}."
    else:
        meta_desc = f"{name} ({year}) for sale. {length_str}, {engines}. Price: {format_price_en(price)}. Viewing in {location}."

    # Labels
    L = _get_labels(lang)

    # Badges HTML
    badge_html = ""
    if badges:
        badge_parts = []
        for b in badges:
            label = BADGE_LABELS.get(lang, {}).get(b, b)
            css = BADGE_CSS.get(b, "")
            badge_parts.append(f'<span class="badge {css}">{label}</span>')
        badge_html = " ".join(badge_parts) + "\n          "

    # Type label
    type_label = TYPE_LABELS.get(lang, {}).get(boat_type, boat_type.capitalize())

    # Specs table rows
    spec_rows = ""
    for key, val in specs.items():
        spec_rows += f'\n<tr class="border-b border-dark-border/30"><td class="py-3 pr-6 text-txt-dark-2/60 text-sm font-light">{key}</td><td class="py-3 text-txt-dark text-sm">{val}</td></tr>'

    # Gallery
    gallery_html = build_gallery_html(slug, name, gallery_files)

    # Similar boats
    similar = compute_similar_boats(boat, all_boats)
    similar_html = _build_similar_html(similar, lang)

    # WhatsApp text
    wa_text = urllib.parse.quote(f"Hola, me interesa el {name}", safe="") if is_es else urllib.parse.quote(f"Hi, I'm interested in the {name}", safe="")

    # Length display
    length_display = f"{length}m" if length == int(length) else f"{length}m"

    # Year + length line
    year_length = f"{year} · {length_display}" if year and length else str(year)

    return f"""<!-- GENERATED by scripts/build_site.py — NO EDITAR MANUALMENTE.
     Fuente de verdad: static/site/data/boats/{slug}.json + manifest.json
     Para editar: usar el admin (/internal/admin/) o modificar el JSON y ejecutar build_site.py -->
<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name} — {year} · {price_title} — SentYacht</title>
  <meta name="description" content="{meta_desc}">
  <link rel="canonical" href="https://sentyacht.es{own_path}">
  <link rel="alternate" hreflang="es" href="https://sentyacht.es/es/barcos/{slug}/">
  <link rel="alternate" hreflang="en" href="https://sentyacht.es/en/boats/{slug}/">
  <meta property="og:title" content="{name} — SentYacht">
  <meta property="og:description" content="{meta_desc}">
  <meta property="og:type" content="product">
  <meta property="og:url" content="https://sentyacht.es{own_path}">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90' fill='%230077CC'>S</text></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {{
      theme: {{ extend: {{
        colors: {{
          'dark-base':'#0B1220','dark-surface':'#142233','dark-floating':'#1A2D45','dark-border':'#1E3148',
          'light-base':'#FAF7F2','light-surface':'#FFFFFF','light-border':'#E8E0D4',
          'brand-blue':'#0077CC','brand-blue-hover':'#005FA3','brand-gold':'#C9A96E','brand-gold-hover':'#B8954F',
          'txt-dark':'#F2EDE8','txt-dark-2':'#8A9BB5','txt-light':'#1A1A2E','txt-light-2':'#5C6370',
        }},
        fontFamily: {{ serif:['Cormorant Garamond','Georgia','serif'], sans:['Inter','system-ui','sans-serif'] }},
      }}}}
    }}
  </script>
  <link rel="stylesheet" href="/styles.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/glightbox/dist/css/glightbox.min.css">
    <!-- Meta Pixel Code -->
    <script>
    !function(f,b,e,v,n,t,s)
    {{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
    n.callMethod.apply(n,arguments):n.queue.push(arguments)}};
    if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
    n.queue=[];t=b.createElement(e);t.async=!0;
    t.src=v;s=b.getElementsByTagName(e)[0];
    s.parentNode.insertBefore(t,s)}}(window, document,'script',
    'https://connect.facebook.net/en_US/fbevents.js');
    fbq('init', '2069294577261810');
    fbq('track', 'PageView');
    </script>
    <noscript><img height="1" width="1" style="display:none"
    src="https://www.facebook.com/tr?id=2069294577261810&ev=PageView&noscript=1"
    /></noscript>
    <!-- End Meta Pixel Code -->
</head>
<body class="bg-dark-base text-txt-dark font-sans antialiased">

  <!-- Nav -->
  <nav id="navbar" class="fixed top-0 left-0 right-0 z-50 nav-solid" style="transition: background-color 0.4s, box-shadow 0.4s;">
    <div class="max-w-7xl mx-auto px-6 lg:px-8">
      <div class="flex items-center justify-between h-20">
        <a href="{home}" class="flex items-center" aria-label="SentYacht"><img src="/assets/logo.png" alt="SentYacht" class="h-8 sm:h-9"></a>
        <div class="hidden md:flex items-center gap-10">
          <a href="{catalog}" class="text-[13px] tracking-[0.15em] uppercase text-txt-dark/70 hover:text-txt-dark font-light" style="transition:color 0.3s;">{L["nav_catalog"]}</a>
          <a href="{home}{L["nav_about_hash"]}" class="text-[13px] tracking-[0.15em] uppercase text-txt-dark/70 hover:text-txt-dark font-light" style="transition:color 0.3s;">{L["nav_about"]}</a>
          <a href="{home}{L["nav_contact_hash"]}" class="text-[13px] tracking-[0.15em] uppercase text-txt-dark/70 hover:text-txt-dark font-light" style="transition:color 0.3s;">{L["nav_contact"]}</a>
          <a href="{alt_path}" class="text-[13px] tracking-[0.15em] uppercase text-brand-gold/70 hover:text-brand-gold font-light" style="transition:color 0.3s;">{alt_lang.upper()}</a>
          <a href="tel:+34609865215" class="btn-primary !py-2.5 !px-6 !text-[12px] ml-2">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg>
            {L["nav_call"]}
          </a>
        </div>
      </div>
    </div>
  </nav>

  <main class="pt-20">

  <!-- Hero Gallery -->
  <section class="bg-dark-surface">
    <div class="max-w-7xl mx-auto px-6 lg:px-8 py-8">
      <!-- Breadcrumb -->
      <nav class="mb-6" aria-label="Breadcrumb">
        <ol class="flex items-center gap-2 text-[12px] text-txt-dark-2/50">
          <li><a href="{home}" class="hover:text-brand-blue" style="transition:color 0.3s;">{L["bread_home"]}</a></li>
          <li class="text-txt-dark-2/30">/</li>
          <li><a href="{catalog}" class="hover:text-brand-blue" style="transition:color 0.3s;">{L["bread_catalog"]}</a></li>
          <li class="text-txt-dark-2/30">/</li>
          <li class="text-txt-dark-2/80">{name}</li>
        </ol>
      </nav>
{gallery_html}
    </div>
  </section>

  <!-- Boat Info -->
  <section class="max-w-7xl mx-auto px-6 lg:px-8 py-12 lg:py-16">
    <div class="grid grid-cols-1 lg:grid-cols-5 gap-12 lg:gap-16">

      <!-- Left: Details -->
      <div class="lg:col-span-3">
        <div class="flex flex-wrap items-center gap-3 mb-4">
          {badge_html}<span class="text-[11px] font-light uppercase tracking-[0.2em] text-txt-dark-2/60">{brand} · {type_label} · {location}</span>
        </div>
        <h1 class="font-serif text-3xl sm:text-4xl lg:text-5xl text-txt-dark tracking-[-0.03em] leading-[1.1] font-light">{name}</h1>
        <div class="flex items-baseline gap-4 mt-4 mb-8">
          <span class="font-serif text-2xl sm:text-3xl text-brand-gold font-light tracking-tight" style="font-feature-settings:'tnum';">{price_body}</span>
          <span class="text-sm text-txt-dark-2/50">{year_length}</span>
        </div>

        <!-- Description -->
        <div class="mb-10">
          <h2 class="text-xs tracking-[0.15em] uppercase text-txt-dark-2/60 mb-4 font-medium">{L["desc_title"]}</h2>
          <p class="text-txt-dark/80 leading-[1.8] text-[15px] font-light">{description}</p>
        </div>

        <!-- Specs Table -->
        <div>
          <h2 class="text-xs tracking-[0.15em] uppercase text-txt-dark-2/60 mb-4 font-medium">{L["specs_title"]}</h2>
          <table class="w-full">
            <tbody>
              {spec_rows}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Right: Contact Form -->
      <div class="lg:col-span-2">
        <div class="bg-dark-surface border border-dark-border/40 rounded-sm p-6 lg:p-8 sticky top-28">
          <h3 class="font-serif text-xl text-txt-dark mb-2">{L["form_title"]}</h3>
          <p class="text-txt-dark-2/50 text-sm font-light mb-6">{L["form_sub"]}</p>
          <form action="https://formspree.io/f/YOUR_FORM_ID" method="POST" class="space-y-4">
            <input type="hidden" name="boat" value="{name} ({slug})">
            <input type="text" name="name" placeholder="{L["form_name"]}" required class="form-input">
            <input type="email" name="email" placeholder="{L["form_email"]}" required class="form-input">
            <input type="tel" name="phone" placeholder="{L["form_phone"]}" class="form-input">
            <textarea name="message" placeholder="{L["form_msg"]}" rows="3" class="form-input" style="resize:vertical;"></textarea>
            <button type="submit" class="btn-gold w-full">{L["form_btn"]}</button>
          </form>
          <!-- Quick contact -->
          <div class="mt-6 pt-6 border-t border-dark-border/30 space-y-3">
            <a href="tel:+34609865215" class="flex items-center gap-3 text-sm text-txt-dark-2/70 hover:text-brand-blue" style="transition:color 0.3s;">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg>
              +34 609 865 215
            </a>
            <a href="https://wa.me/34609865215?text={wa_text}" target="_blank" rel="noopener" class="flex items-center gap-3 text-sm text-txt-dark-2/70 hover:text-brand-blue" style="transition:color 0.3s;">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.625.846 5.059 2.284 7.034L.789 23.492a.5.5 0 00.611.611l4.458-1.495A11.96 11.96 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-2.387 0-4.592-.838-6.316-2.234l-.44-.367-3.265 1.094 1.094-3.265-.367-.44A9.96 9.96 0 012 12C2 6.486 6.486 2 12 2s10 4.486 10 10-4.486 10-10 10z"/></svg>
              WhatsApp
            </a>
          </div>
        </div>
      </div>
    </div>
  </section>

{similar_html}

  </main>

  <!-- Footer -->
  <footer class="border-t border-dark-border/30 bg-dark-base">
    <div class="max-w-7xl mx-auto px-6 lg:px-8 py-16">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-12 items-start">
        <div>
          <a href="{home}" class="inline-block mb-4"><img src="/assets/logo.png" alt="SentYacht" class="h-7"></a>
          <p class="text-txt-dark-2/50 text-sm font-light leading-relaxed">{L["footer_tagline"]}</p>
        </div>
        <div>
          <h4 class="text-xs tracking-[0.2em] uppercase text-txt-dark-2/50 mb-5">{L["footer_nav"]}</h4>
          <div class="flex flex-col gap-3">
            <a href="{home}" class="text-txt-dark-2/60 text-sm font-light hover:text-brand-blue" style="transition:color 0.3s;">{L["footer_home"]}</a>
            <a href="{catalog}" class="text-txt-dark-2/60 text-sm font-light hover:text-brand-blue" style="transition:color 0.3s;">{L["footer_catalog"]}</a>
            <a href="{home}{L["nav_contact_hash"]}" class="text-txt-dark-2/60 text-sm font-light hover:text-brand-blue" style="transition:color 0.3s;">{L["footer_contacto"]}</a>
          </div>
        </div>
        <div>
          <h4 class="text-xs tracking-[0.2em] uppercase text-txt-dark-2/50 mb-5">{L["footer_contact"]}</h4>
          <div class="flex flex-col gap-3 text-sm font-light">
            <p class="text-txt-dark-2/60">Port Esportiu, Local 49</p>
            <p class="text-txt-dark-2/60">El Masnou, 08320, Barcelona</p>
            <a href="tel:+34609865215" class="text-txt-dark-2/60 hover:text-brand-blue" style="transition:color 0.3s;">+34 609 865 215</a>
            <a href="mailto:jordi@sentyacht.es" class="text-txt-dark-2/60 hover:text-brand-blue" style="transition:color 0.3s;">jordi@sentyacht.es</a>
          </div>
        </div>
        <div>
          <h4 class="text-xs tracking-[0.2em] uppercase text-txt-dark-2/50 mb-5">{L["footer_legal"]}</h4>
          <div class="flex flex-col gap-3 text-sm font-light">
            <a href="{L["legal_aviso"]}" class="text-txt-dark-2/60 hover:text-brand-blue" style="transition:color 0.3s;">{L["footer_aviso"]}</a>
            <a href="{L["legal_priv"]}" class="text-txt-dark-2/60 hover:text-brand-blue" style="transition:color 0.3s;">{L["footer_priv"]}</a>
            <a href="{L["legal_cookies"]}" class="text-txt-dark-2/60 hover:text-brand-blue" style="transition:color 0.3s;">{L["footer_cookies"]}</a>
          </div>
        </div>
      </div>
      <div class="mt-16 pt-8 border-t border-dark-border/20 flex flex-col sm:flex-row items-center justify-between gap-4">
        <p class="text-txt-dark-2/25 text-xs font-light">{L["footer_copy"]}</p>
        <p class="text-txt-dark-2/25 text-xs font-light">Puerto Deportivo El Masnou, Barcelona</p>
      </div>
    </div>
  </footer>

  <!-- JSON-LD -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "{name}",
    "description": "{_escape_json_ld(description)}",
    "brand": {{ "@type": "Brand", "name": "{brand}" }},
    "offers": {{
      "@type": "Offer",
      "price": "{price}",
      "priceCurrency": "EUR",
      "availability": "https://schema.org/InStock",
      "seller": {{ "@type": "Organization", "name": "SentYacht" }}
    }},
    "manufacturer": {{ "@type": "Organization", "name": "{brand}" }},
    "model": "{name}",
    "productionDate": "{year}"
  }}
  </script>

  <script src="https://cdn.jsdelivr.net/npm/glightbox/dist/js/glightbox.min.js"></script>
  <script>GLightbox({{ selector: '.glightbox' }});</script>

  <script src="/config.js"></script>
  <script src="/shared.js"></script>

</body>
</html>"""


def _escape_json_ld(text: str) -> str:
    """Escape text for JSON-LD embedded in HTML."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _build_similar_html(similar: list[dict], lang: str) -> str:
    """Build similar boats section HTML."""
    if not similar:
        return ""

    is_es = lang == "es"
    title = "Embarcaciones similares" if is_es else "Similar Yachts"
    view_prefix = "Ver" if is_es else "View"
    boat_path = "es/barcos" if is_es else "en/boats"

    lines = ['  <!-- Similar Boats -->']
    lines.append('  <section class="py-16 bg-dark-surface border-t border-dark-border/30">')
    lines.append('    <div class="max-w-7xl mx-auto px-6 lg:px-8">')
    lines.append(f'      <h2 class="font-serif text-2xl text-txt-dark tracking-[-0.03em] mb-8">{title}</h2>')
    lines.append('      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">')

    for s in similar:
        s_slug = s["slug"]
        s_name = s["name"]
        s_brand = s["brand"]
        s_year = s["year"]
        s_length = s.get("length", 0)
        s_price = format_price_es(s.get("price", 0))
        s_images = s.get("images", [])
        s_img = s_images[0] if s_images else ""
        s_length_str = f"{s_length}m" if s_length == int(s_length) else f"{s_length}m"

        lines.append(f'        <a href="/{boat_path}/{s_slug}/" class="boat-card" aria-label="{view_prefix} {s_name}">')
        lines.append(f'      <div class="boat-card-image"><img src="/assets/{s_img}" alt="{s_name}" loading="lazy"></div>')
        lines.append('      <div class="p-5">')
        lines.append('        <div class="flex items-baseline justify-between mb-2">')
        lines.append(f'          <span class="text-[11px] font-light uppercase tracking-[0.18em] text-txt-light-2">{s_brand} · {s_year}</span>')
        lines.append(f'          <span class="text-[11px] text-txt-light-2/50">{s_length_str}</span>')
        lines.append('        </div>')
        lines.append(f'        <h3 class="font-serif text-lg text-txt-light font-light tracking-tight leading-snug mb-2">{s_name}</h3>')
        lines.append(f'        <span class="font-serif text-lg text-brand-gold font-light" style="font-feature-settings:\'tnum\';">{s_price}</span>')
        lines.append('      </div>')
        lines.append('    </a>')

    lines.append('      </div>')
    lines.append('    </div>')
    lines.append('  </section>')

    return "\n".join(lines)


def _get_labels(lang: str) -> dict:
    """Get all UI labels for a given language."""
    if lang == "es":
        return {
            "nav_catalog": "Embarcaciones",
            "nav_about": "Nosotros",
            "nav_about_hash": "#nosotros",
            "nav_contact": "Contacto",
            "nav_contact_hash": "#contacto",
            "nav_call": "Llamar",
            "bread_home": "Inicio",
            "bread_catalog": "Embarcaciones",
            "desc_title": "Descripción",
            "specs_title": "Especificaciones",
            "form_title": "Solicitar información",
            "form_sub": "Le contactaremos en menos de 48 horas.",
            "form_name": "Nombre completo",
            "form_email": "Email",
            "form_phone": "Teléfono",
            "form_msg": "Su mensaje...",
            "form_btn": "Enviar consulta",
            "footer_tagline": "Grandes embarcaciones desde 1976.<br>El Masnou, Barcelona.",
            "footer_nav": "Navegación",
            "footer_contact": "Contacto",
            "footer_legal": "Legal",
            "footer_home": "Inicio",
            "footer_catalog": "Embarcaciones",
            "footer_contacto": "Contacto",
            "footer_aviso": "Aviso Legal",
            "footer_priv": "Política de Privacidad",
            "footer_cookies": "Política de Cookies",
            "footer_copy": "© 2026 SentYacht. Todos los derechos reservados.",
            "legal_aviso": "/es/aviso-legal/",
            "legal_priv": "/es/politica-de-privacidad/",
            "legal_cookies": "/es/politica-de-cookies/",
        }
    return {
        "nav_catalog": "Yachts",
        "nav_about": "About",
        "nav_about_hash": "#about",
        "nav_contact": "Contact",
        "nav_contact_hash": "#contact",
        "nav_call": "Call",
        "bread_home": "Home",
        "bread_catalog": "Yachts",
        "desc_title": "Description",
        "specs_title": "Specifications",
        "form_title": "Request Information",
        "form_sub": "We will contact you within 48 hours.",
        "form_name": "Full name",
        "form_email": "Email",
        "form_phone": "Phone",
        "form_msg": "Your message...",
        "form_btn": "Send enquiry",
        "footer_tagline": "Premium yachts since 1976.<br>El Masnou, Barcelona.",
        "footer_nav": "Navigation",
        "footer_contact": "Contact",
        "footer_legal": "Legal",
        "footer_home": "Home",
        "footer_catalog": "Yachts",
        "footer_contacto": "Contact",
        "footer_aviso": "Legal Notice",
        "footer_priv": "Privacy Policy",
        "footer_cookies": "Cookie Policy",
        "footer_copy": "© 2026 SentYacht. All rights reserved.",
        "legal_aviso": "/en/legal-notice/",
        "legal_priv": "/en/privacy-policy/",
        "legal_cookies": "/en/cookie-policy/",
    }


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

def main():
    print("=== Loading boat data ===")
    boats = load_all_boats()
    print(f"  {len(boats)} boats loaded")

    # Load manifests
    manifests = {}
    for boat in boats:
        slug = boat["slug"]
        files = load_manifest(slug)
        manifests[slug] = files
        if files:
            print(f"  {slug}: {len(files)} gallery images")
        else:
            print(f"  {slug}: no gallery images")

    # 1. Generate boats.js
    print("\n=== Generating boats.js ===")
    boats_js = build_boats_js(boats)
    boats_js_path = os.path.join(SITE_DIR, "boats.js")
    with open(boats_js_path, "w", encoding="utf-8") as f:
        f.write(boats_js)
    print(f"  Written: boats.js ({len(boats_js)} bytes)")

    # 2. Generate detail pages
    print("\n=== Generating detail pages ===")
    page_count = 0
    for boat in boats:
        slug = boat["slug"]
        gallery = manifests.get(slug, [])
        for lang in ("es", "en"):
            html = build_detail_page(boat, lang, gallery, boats)
            if lang == "es":
                page_dir = os.path.join(SITE_DIR, "es", "barcos", slug)
            else:
                page_dir = os.path.join(SITE_DIR, "en", "boats", slug)
            os.makedirs(page_dir, exist_ok=True)
            page_path = os.path.join(page_dir, "index.html")
            with open(page_path, "w", encoding="utf-8") as f:
                f.write(html)
            page_count += 1

    print(f"  Written: {page_count} detail pages")
    print(f"\n=== Build complete: {len(boats)} boats, {page_count} pages, 1 boats.js ===")


if __name__ == "__main__":
    main()
