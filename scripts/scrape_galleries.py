"""Scrape boat photo galleries from cosasdebarcos.com for SentYacht listings.

Usage: python scripts/scrape_galleries.py
Requires: pip install playwright && python -m playwright install chromium

Output:
  static/site/assets/boats/<slug>/01.jpg, 02.jpg, ...
  static/site/assets/boats/manifest.json
"""

import json
import os
import re
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE_URL = "https://www.cosasdebarcos.com"
INDEX_URL = f"{BASE_URL}/barcos/palabra-clave-sentyacht/"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "site", "assets", "boats")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

SLUG_MAP = {
    "1972-finnyacht-finm-cleaper-35-9536978": "finnyacht-35-1972",
    "1981-ketch-nordic-36-classic-10032207": "ketch-nordic-36-classic-1981",
    "1990-fjord-900-9308103": "fjord-900-1990",
    "1993-astondoa-53-glx-9104508": "astondoa-53-glx-1993",
    "1996-rodman-900-fly-9666175": "rodman-900-flybridge-1996",
    "2002-astondoa-39-9367545": "astondoa-39-2002",
    "2002-grand-banks-38-eastbay-ex-10042802": "grand-banks-38-eastbay-ex-2002",
    "2003-astondoa-72-glx-10007712": "astondoa-72-glx-2003",
    "2004-sunseeker-manhattan-50-9589953": "sunseeker-manhattan-50-2004",
    "2006-navalia-60-10100469": "navalia-60-2006",
    "2007-hanse-470-10101704": "hanse-470-2007",
    "2008-astondoa-82-glx-10101664": "astondoa-82-glx-2008",
}


def download_image(url, path):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            if len(data) < 1000:
                return False
            with open(path, "wb") as f:
                f.write(data)
            return True
    except Exception as e:
        print(f"    DOWNLOAD FAILED: {url} -> {e}")
        return False


def extract_images(page):
    """Extract unique full-size boatsgroup image URLs, in gallery order."""
    # Get all boatsgroup img srcs from the page
    raw = page.evaluate("""() => {
        const urls = [];
        document.querySelectorAll('img').forEach(img => {
            const src = img.src || '';
            if (src.includes('boatsgroup.com') && src.includes('.jpg')) {
                urls.push(src);
            }
        });
        return urls;
    }""")

    # Deduplicate by base filename (without query params and size suffix)
    seen = set()
    unique = []
    for url in raw:
        # Extract the base image identifier (filename without query params)
        base = url.split("?")[0]
        # Normalize: extract the unique image filename
        # Pattern: .../2008-astondoa-82-glx-power-10101664-20260305021859320-1.jpg
        match = re.search(r'(/\d{4}-[^?]+\.jpg)', base)
        if match:
            key = match.group(1)
        else:
            key = base

        if key not in seen:
            seen.add(key)
            # Build full-size URL: remove query params to get original
            full_url = base
            unique.append(full_url)

    return unique


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    manifest = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)

        # Step 1: Get listing URLs
        print("Fetching index page...")
        page.goto(INDEX_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # Accept cookies
        try:
            page.locator("#onetrust-accept-btn-handler").click(timeout=3000)
            page.wait_for_timeout(1000)
        except Exception:
            pass

        listing_paths = page.evaluate("""() => {
            const paths = new Set();
            document.querySelectorAll('a[href*="/barco/"]').forEach(a => {
                const match = a.href.match(/\\/barco\\/[^/]+\\//);
                if (match) paths.add(match[0]);
            });
            return Array.from(paths).sort();
        }""")
        print(f"Found {len(listing_paths)} listings\n")

        for path in listing_paths:
            path_key = path.strip("/").replace("barco/", "")
            slug = SLUG_MAP.get(path_key)
            if not slug:
                print(f"SKIP: no slug mapping for {path_key}")
                continue

            url = BASE_URL + path
            print(f"--- {slug} ---")
            print(f"    URL: {url}")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)
            except Exception as e:
                print(f"    FETCH FAILED: {e}")
                manifest.append({
                    "slug": slug, "url": url, "status": "FAILED",
                    "reason": str(e), "photos": 0, "files": [],
                })
                continue

            title = page.evaluate("() => document.querySelector('h1')?.textContent?.trim() || ''")
            images = extract_images(page)
            print(f"    Title: {title}")
            print(f"    Found {len(images)} unique images")

            if not images:
                manifest.append({
                    "slug": slug, "name": title, "url": url,
                    "status": "FAILED", "reason": "no images found",
                    "photos": 0, "files": [],
                })
                continue

            boat_dir = os.path.join(OUTPUT_DIR, slug)
            os.makedirs(boat_dir, exist_ok=True)

            files = []
            failed = 0
            for i, img_url in enumerate(images, 1):
                filename = f"{i:02d}.jpg"
                filepath = os.path.join(boat_dir, filename)
                if download_image(img_url, filepath):
                    size_kb = os.path.getsize(filepath) // 1024
                    files.append(filename)
                    print(f"    {filename} ({size_kb}KB)")
                else:
                    failed += 1

            status = "OK_COMPLETE" if failed == 0 and len(files) > 0 else "OK_PARTIAL" if len(files) > 0 else "FAILED"
            manifest.append({
                "slug": slug,
                "name": title,
                "url": url,
                "status": status,
                "photos": len(files),
                "failed_downloads": failed,
                "files": files,
            })

            time.sleep(1)

        browser.close()

    # Write manifest
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for entry in manifest:
        print(f"  {entry['status']:12s}  {entry['slug']:45s}  {entry['photos']} photos")

    ok = sum(1 for e in manifest if e["status"] == "OK_COMPLETE")
    partial = sum(1 for e in manifest if e["status"] == "OK_PARTIAL")
    fail = sum(1 for e in manifest if e["status"] == "FAILED")
    total_photos = sum(e["photos"] for e in manifest)
    print(f"\n  OK_COMPLETE: {ok}  |  OK_PARTIAL: {partial}  |  FAILED: {fail}")
    print(f"  Total photos: {total_photos}")
    print(f"\nManifest: {manifest_path}")
    print("Web publica: NO MODIFICADA")


if __name__ == "__main__":
    main()
