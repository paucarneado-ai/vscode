"""Replace single hero image with full gallery in all 24 boat detail pages.

Replaces the <!-- Main Image --> block with:
- Hero image (01.jpg) in same aspect-[16/9]
- Thumbnail grid below with all gallery images
- All linked as glightbox with data-gallery for slideshow

Usage: python scripts/integrate_galleries.py
"""

import json
import os
import re

SITE_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "site")
BOATS_DIR = os.path.join(SITE_DIR, "assets", "boats")

# Map slug -> boat name (from manifests)
def load_boat_names():
    names = {}
    for slug in os.listdir(BOATS_DIR):
        manifest_path = os.path.join(BOATS_DIR, slug, "manifest.json")
        if os.path.isfile(manifest_path):
            with open(manifest_path) as f:
                data = json.load(f)
            # Extract clean name from title like "2008 Astondoa 82 GLX | 25m"
            raw = data.get("name", slug)
            name = re.sub(r"^\d{4}\s+", "", raw).split("|")[0].strip()
            names[slug] = name or slug
    return names


def get_gallery_files(slug):
    """Return sorted list of jpg files for a boat."""
    boat_dir = os.path.join(BOATS_DIR, slug)
    if not os.path.isdir(boat_dir):
        return []
    return sorted(f for f in os.listdir(boat_dir) if f.endswith(".jpg"))


def build_gallery_html(slug, alt_name, files):
    """Build the gallery HTML that replaces <!-- Main Image --> block."""
    if not files:
        return None

    hero = files[0]
    thumbs = files[1:]
    base_path = f"/assets/boats/{slug}"

    lines = []
    lines.append(f'      <!-- Gallery -->')
    # Hero image
    lines.append(f'      <a href="{base_path}/{hero}" class="glightbox block aspect-[16/9] overflow-hidden rounded-sm" data-gallery="boat">')
    lines.append(f'        <img src="{base_path}/{hero}" alt="{alt_name}" class="w-full h-full object-cover" style="transition: transform 0.6s cubic-bezier(0.16,1,0.3,1);" onmouseover="this.style.transform=\'scale(1.03)\'" onmouseout="this.style.transform=\'scale(1)\'">')
    lines.append(f'      </a>')

    if thumbs:
        lines.append(f'      <div class="grid grid-cols-4 sm:grid-cols-6 gap-2 mt-3">')
        for i, thumb in enumerate(thumbs):
            lazy = ' loading="lazy"' if i >= 4 else ''
            lines.append(f'        <a href="{base_path}/{thumb}" class="glightbox aspect-[4/3] overflow-hidden rounded-sm" data-gallery="boat"><img src="{base_path}/{thumb}" alt="{alt_name}" class="w-full h-full object-cover hover:opacity-80" style="transition:opacity 0.3s;"{lazy}></a>')
        lines.append(f'      </div>')

    return "\n".join(lines)


def process_file(filepath, slug, alt_name, files):
    """Replace the Main Image block in a single HTML file."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Match from <!-- Main Image --> to the closing </a> + newline before </div>
    pattern = r'      <!-- Main Image -->\n      <a href="[^"]*" class="glightbox[^>]*>\n        <img [^>]*>\n      </a>'
    match = re.search(pattern, content)
    if not match:
        return False, "pattern not found"

    gallery_html = build_gallery_html(slug, alt_name, files)
    if not gallery_html:
        return False, "no gallery files"

    new_content = content[:match.start()] + gallery_html + content[match.end():]

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True, f"{len(files)} images"


def main():
    names = load_boat_names()
    results = []

    # Process all ES and EN pages
    page_dirs = [
        ("es", os.path.join(SITE_DIR, "es", "barcos")),
        ("en", os.path.join(SITE_DIR, "en", "boats")),
    ]

    for lang, base_dir in page_dirs:
        if not os.path.isdir(base_dir):
            continue
        for slug in sorted(os.listdir(base_dir)):
            filepath = os.path.join(base_dir, slug, "index.html")
            if not os.path.isfile(filepath):
                continue

            files = get_gallery_files(slug)
            alt_name = names.get(slug, slug)

            if not files:
                print(f"  SKIP  {lang}/{slug}: no gallery")
                results.append((lang, slug, "SKIP", "no gallery"))
                continue

            ok, msg = process_file(filepath, slug, alt_name, files)
            status = "OK" if ok else "FAIL"
            print(f"  {status:4s}  {lang}/{slug}: {msg}")
            results.append((lang, slug, status, msg))

    # Summary
    ok_count = sum(1 for _, _, s, _ in results if s == "OK")
    fail_count = sum(1 for _, _, s, _ in results if s == "FAIL")
    skip_count = sum(1 for _, _, s, _ in results if s == "SKIP")
    print(f"\nUpdated: {ok_count}  |  Failed: {fail_count}  |  Skipped: {skip_count}")
    print("Web publica modificada: SI (fichas de barcos actualizadas)")


if __name__ == "__main__":
    main()
