"""Scrape all 12 SentYacht boat galleries from cosasdebarcos.com.

Usage: python scripts/scrape_all_galleries.py
Requires: Playwright with chromium (headed mode to bypass Cloudflare)
"""

import json
import os
import re
import struct
import time

from playwright.sync_api import sync_playwright

BASE_URL = "https://www.cosasdebarcos.com"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "site", "assets", "boats")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

BOATS = [
    {"path": "/barco/2008-astondoa-82-glx-10101664/", "slug": "astondoa-82-glx-2008"},
    {"path": "/barco/2003-astondoa-72-glx-10007712/", "slug": "astondoa-72-glx-2003"},
    {"path": "/barco/1993-astondoa-53-glx-9104508/", "slug": "astondoa-53-glx-1993"},
    {"path": "/barco/2002-astondoa-39-9367545/", "slug": "astondoa-39-2002"},
    {"path": "/barco/2004-sunseeker-manhattan-50-9589953/", "slug": "sunseeker-manhattan-50-2004"},
    {"path": "/barco/2002-grand-banks-38-eastbay-ex-10042802/", "slug": "grand-banks-38-eastbay-ex-2002"},
    {"path": "/barco/2006-navalia-60-10100469/", "slug": "navalia-60-2006"},
    {"path": "/barco/2007-hanse-470-10101704/", "slug": "hanse-470-2007"},
    {"path": "/barco/1996-rodman-900-fly-9666175/", "slug": "rodman-900-flybridge-1996"},
    {"path": "/barco/1990-fjord-900-9308103/", "slug": "fjord-900-1990"},
    {"path": "/barco/1981-ketch-nordic-36-classic-10032207/", "slug": "ketch-nordic-36-classic-1981"},
    {"path": "/barco/1972-finnyacht-finm-cleaper-35-9536978/", "slug": "finnyacht-35-1972"},
]


def jpeg_dimensions(path):
    try:
        with open(path, "rb") as f:
            f.read(2)
            while True:
                marker = f.read(2)
                if len(marker) < 2:
                    return None, None
                if marker[0] != 0xFF:
                    return None, None
                if marker[1] in (0xC0, 0xC2):
                    f.read(3)
                    h = struct.unpack(">H", f.read(2))[0]
                    w = struct.unpack(">H", f.read(2))[0]
                    return w, h
                length = struct.unpack(">H", f.read(2))[0]
                f.read(length - 2)
    except Exception:
        return None, None


def scrape_boat(page, boat):
    slug = boat["slug"]
    url = BASE_URL + boat["path"]
    boat_dir = os.path.join(OUTPUT_DIR, slug)

    print(f"\n--- {slug} ---")
    print(f"    URL: {url}")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=120000)

        # Wait for real content or Cloudflare challenge to resolve
        for attempt in range(3):
            try:
                page.wait_for_selector("h1", state="attached", timeout=30000)
                break
            except Exception:
                page_title = page.title()
                if "moment" in page_title.lower() or "challenge" in page_title.lower():
                    print(f"    Cloudflare challenge detected (attempt {attempt+1}), waiting 15s...")
                    time.sleep(15)
                    page.reload(wait_until="domcontentloaded")
                else:
                    raise
        else:
            raise Exception("Cloudflare challenge not resolved after 3 attempts")

        time.sleep(3)
    except Exception as e:
        print(f"    FAILED: page load error: {e}")
        return {"slug": slug, "url": url, "status": "FAILED", "reason": str(e),
                "detected": 0, "downloaded": 0, "files": []}

    # Accept cookies (only needed once but safe to retry)
    try:
        page.locator("#onetrust-accept-btn-handler").click(timeout=2000)
        time.sleep(1)
    except Exception:
        pass

    title = page.evaluate("() => document.querySelector('h1')?.textContent?.trim() || ''")
    print(f"    Title: {title}")

    # Extract unique images from carousel only
    carousel_images = page.evaluate(r"""() => {
        const carousel = document.querySelector('.embla-carousel, [class*=emblaCarousel]');
        if (!carousel) return [];
        const imgs = carousel.querySelectorAll('img');
        const urls = [];
        const seen = new Set();
        imgs.forEach(img => {
            const src = img.src || '';
            if (!src.includes('boatsgroup.com') || !src.includes('.jpg')) return;
            // Extract unique image identifier from URL
            // Pattern A (new): ...-20260305021859320-1.jpg
            // Pattern B (old): ...9104508_20231026012832547_1_XLARGE.jpg
            const base = src.split('?')[0];
            // Use the filename after the last / as unique key
            const filename = base.split('/').pop();
            if (!filename || seen.has(filename)) return;
            seen.add(filename);
            urls.push({ id: filename, url: base });
        });
        return urls;
    }""")

    print(f"    Detected: {len(carousel_images)} unique gallery images")

    if not carousel_images:
        print(f"    FAILED: no carousel images")
        return {"slug": slug, "name": title, "url": url, "status": "FAILED",
                "reason": "no carousel images", "detected": 0, "downloaded": 0, "files": []}

    # Download via browser fetch
    os.makedirs(boat_dir, exist_ok=True)
    files = []
    failed = 0

    for i, img in enumerate(carousel_images, 1):
        filename = f"{i:02d}.jpg"
        filepath = os.path.join(boat_dir, filename)

        try:
            result = page.evaluate("""async (url) => {
                const resp = await fetch(url);
                if (!resp.ok) return { error: resp.status, size: 0 };
                const blob = await resp.blob();
                const buffer = await blob.arrayBuffer();
                const bytes = Array.from(new Uint8Array(buffer));
                return { error: null, size: bytes.length, bytes: bytes };
            }""", img["url"])

            if result["error"]:
                print(f"    {filename} FAILED (HTTP {result['error']})")
                failed += 1
                continue

            if result["size"] < 5000:
                print(f"    {filename} SKIP (too small: {result['size']}B)")
                failed += 1
                continue

            with open(filepath, "wb") as f:
                f.write(bytes(result["bytes"]))

            size_kb = result["size"] // 1024
            files.append(filename)
            print(f"    {filename} {size_kb}KB")

        except Exception as e:
            print(f"    {filename} ERROR: {e}")
            failed += 1

    # Renumber if any gaps (from failed downloads)
    if failed > 0 and files:
        actual_files = sorted(f for f in os.listdir(boat_dir) if f.endswith(".jpg"))
        for new_i, old_name in enumerate(actual_files, 1):
            new_name = f"{new_i:02d}.jpg"
            if old_name != new_name:
                os.rename(os.path.join(boat_dir, old_name), os.path.join(boat_dir, new_name))
        files = [f"{i:02d}.jpg" for i in range(1, len(actual_files) + 1)]

    status = "OK_COMPLETE" if failed == 0 and len(files) > 0 else "OK_PARTIAL" if len(files) > 0 else "FAILED"

    # Write per-boat manifest
    boat_manifest = {
        "slug": slug, "name": title, "url": url, "status": status,
        "detected": len(carousel_images), "downloaded": len(files),
        "failed": failed, "files": files,
    }
    with open(os.path.join(boat_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(boat_manifest, f, indent=2, ensure_ascii=False)

    return boat_manifest


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    manifest = []

    # Process each boat with a fresh browser to avoid Cloudflare session limits
    for i, boat in enumerate(BOATS):
        slug = boat["slug"]
        boat_dir = os.path.join(OUTPUT_DIR, slug)

        # Skip if already successfully scraped
        boat_manifest_path = os.path.join(boat_dir, "manifest.json")
        if os.path.exists(boat_manifest_path):
            with open(boat_manifest_path) as f:
                existing = json.load(f)
            if existing.get("status") == "OK_COMPLETE":
                print(f"\n--- {slug} --- ALREADY COMPLETE, skipping")
                manifest.append(existing)
                continue

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(user_agent=UA)
            page = context.new_page()

            result = scrape_boat(page, boat)
            manifest.append(result)

            browser.close()

        if i < len(BOATS) - 1:
            print(f"    Waiting 5s before next boat...")
            time.sleep(5)

    # Write global manifest
    with open(os.path.join(OUTPUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Validation pass
    print(f"\n{'='*60}")
    print("VALIDATION")
    print(f"{'='*60}")
    issues = []
    for entry in manifest:
        slug = entry["slug"]
        boat_dir = os.path.join(OUTPUT_DIR, slug)
        if not os.path.isdir(boat_dir):
            issues.append(f"{slug}: directory missing")
            continue
        jpgs = sorted(f for f in os.listdir(boat_dir) if f.endswith(".jpg"))
        if not jpgs:
            issues.append(f"{slug}: no images in directory")
            continue
        # Check sequential numbering
        expected = [f"{i:02d}.jpg" for i in range(1, len(jpgs) + 1)]
        if jpgs != expected:
            issues.append(f"{slug}: numbering gap: have {jpgs} expected {expected}")
        # Check for tiny files (likely broken)
        for jpg in jpgs:
            size = os.path.getsize(os.path.join(boat_dir, jpg))
            if size < 5000:
                issues.append(f"{slug}/{jpg}: suspiciously small ({size}B)")
        # Check dimensions of first image
        w, h = jpeg_dimensions(os.path.join(boat_dir, jpgs[0]))
        if w and w < 400:
            issues.append(f"{slug}/{jpgs[0]}: small resolution ({w}x{h})")

    if issues:
        print("ISSUES:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("  No issues found.")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    total_photos = 0
    for entry in manifest:
        total_photos += entry.get("downloaded", 0)
        print(f"  {entry['status']:12s}  {entry['slug']:45s}  {entry.get('downloaded', 0):2d}/{entry.get('detected', 0):2d} photos")

    ok = sum(1 for e in manifest if e["status"] == "OK_COMPLETE")
    partial = sum(1 for e in manifest if e["status"] == "OK_PARTIAL")
    fail = sum(1 for e in manifest if e["status"] == "FAILED")
    print(f"\n  OK_COMPLETE: {ok}  |  OK_PARTIAL: {partial}  |  FAILED: {fail}")
    print(f"  Total photos: {total_photos}")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"\n  Web publica: NO MODIFICADA")


if __name__ == "__main__":
    main()
