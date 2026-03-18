"""Test scrape: single boat gallery with headed browser.
Downloads images through the browser session (bypasses CDN auth).

Usage: python scripts/scrape_test_one.py
"""

import json
import os
import re
import time

from playwright.sync_api import sync_playwright

TEST_URL = "https://www.cosasdebarcos.com/barco/2008-astondoa-82-glx-10101664/"
TEST_SLUG = "astondoa-82-glx-2008"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "site", "assets", "boats", TEST_SLUG)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=UA, accept_downloads=True)
        page = context.new_page()

        print(f"Navigating to {TEST_URL}")
        page.goto(TEST_URL, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_selector("h1", state="attached", timeout=60000)
        time.sleep(5)

        # Accept cookies
        try:
            page.locator("#onetrust-accept-btn-handler").click(timeout=3000)
            time.sleep(1)
        except Exception:
            pass

        title = page.evaluate("() => document.querySelector('h1')?.textContent?.trim() || ''")
        print(f"Title: {title}")

        # Extract images ONLY from the main carousel (embla-carousel)
        # Each carousel slide has one real gallery image
        carousel_images = page.evaluate("""() => {
            const carousel = document.querySelector('.embla-carousel, [class*=emblaCarousel]');
            if (!carousel) return [];
            const imgs = carousel.querySelectorAll('img');
            const urls = [];
            const seen = new Set();
            imgs.forEach(img => {
                const src = img.src || '';
                if (!src.includes('boatsgroup.com') || !src.includes('.jpg')) return;
                // Extract the unique image identifier (timestamp-number before .jpg)
                const match = src.match(/(\\d{17}-\\d+)\\.jpg/);
                if (!match) return;
                const imageId = match[1];
                if (seen.has(imageId)) return;
                seen.add(imageId);
                // Build full-size URL: strip query params
                const fullUrl = src.split('?')[0];
                urls.push({ id: imageId, url: fullUrl });
            });
            return urls;
        }""")

        print(f"Carousel images (unique): {len(carousel_images)}")

        if not carousel_images:
            print("FAILED: no carousel images found")
            browser.close()
            return

        # Download each image using the browser's authenticated session
        files = []
        discarded = 0
        for i, img in enumerate(carousel_images, 1):
            filename = f"{i:02d}.jpg"
            filepath = os.path.join(OUTPUT_DIR, filename)

            try:
                # Use page.evaluate + fetch to download through the browser session
                result = page.evaluate("""async (url) => {
                    const resp = await fetch(url);
                    if (!resp.ok) return { error: resp.status, size: 0 };
                    const blob = await resp.blob();
                    const buffer = await blob.arrayBuffer();
                    const bytes = Array.from(new Uint8Array(buffer));
                    return { error: null, size: bytes.length, bytes: bytes };
                }""", img["url"])

                if result["error"]:
                    print(f"  {filename}  FAILED (HTTP {result['error']})")
                    discarded += 1
                    continue

                size = result["size"]
                if size < 5000:
                    print(f"  {filename}  SKIP (too small: {size}B, likely placeholder)")
                    discarded += 1
                    continue

                # Write bytes to file
                with open(filepath, "wb") as f:
                    f.write(bytes(result["bytes"]))

                size_kb = size // 1024
                files.append({"file": filename, "size_kb": size_kb, "image_id": img["id"]})
                print(f"  {filename}  {size_kb}KB")

            except Exception as e:
                print(f"  {filename}  ERROR: {e}")
                discarded += 1

        browser.close()

    # Write manifest
    manifest = {
        "slug": TEST_SLUG,
        "name": title,
        "url": TEST_URL,
        "status": "OK_COMPLETE" if discarded == 0 and len(files) > 0 else "OK_PARTIAL" if len(files) > 0 else "FAILED",
        "gallery_detected": len(carousel_images),
        "downloaded": len(files),
        "discarded": discarded,
        "files": [f["file"] for f in files],
        "sizes_kb": [f["size_kb"] for f in files],
    }
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"Boat:      {title}")
    print(f"Slug:      {TEST_SLUG}")
    print(f"Detected:  {len(carousel_images)} unique gallery images")
    print(f"Downloaded: {len(files)}")
    print(f"Discarded: {discarded}")
    if files:
        sizes = [f["size_kb"] for f in files]
        print(f"Size range: {min(sizes)}KB - {max(sizes)}KB")
        print(f"Total size: {sum(sizes)}KB")
    print(f"Output:    {OUTPUT_DIR}")
    print(f"Status:    {manifest['status']}")
    print(f"Web publica: NO MODIFICADA")


if __name__ == "__main__":
    main()
