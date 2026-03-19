"""One-time migration: extract boat data from boats.js into per-boat JSON files.

Reads the boats array from static/site/boats.js, converts each entry
to a standalone JSON file at static/site/data/boats/{slug}.json.

Usage: python scripts/migrate_boats_to_json.py
"""

import json
import os
import re
import sys

SITE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "static", "site"))
BOATS_JS_PATH = os.path.join(SITE_DIR, "boats.js")
DATA_DIR = os.path.join(SITE_DIR, "data", "boats")


def extract_boats_array(js_content: str) -> str:
    """Extract the text of the boats array from boats.js."""
    # Find `const boats = [` ... `];`
    match = re.search(r"const boats\s*=\s*\[", js_content)
    if not match:
        raise ValueError("Could not find 'const boats = [' in boats.js")

    start = match.end()
    # Find the matching ];
    depth = 1
    i = start
    while i < len(js_content) and depth > 0:
        ch = js_content[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        elif ch in ('"', "'"):
            # Skip string literals
            quote = ch
            i += 1
            while i < len(js_content) and js_content[i] != quote:
                if js_content[i] == "\\":
                    i += 1  # skip escaped char
                i += 1
        i += 1

    return js_content[start : i - 1]  # content between [ and ]


def js_to_json(js_text: str) -> str:
    """Convert JS object literal syntax to JSON.

    Handles: unquoted keys, single-quoted strings, trailing commas.
    """
    result = js_text

    # Convert single-quoted strings to double-quoted (simple cases)
    # This is safe because boats.js doesn't use single quotes inside strings
    result = re.sub(r"'([^']*)'", r'"\1"', result)

    # Quote unquoted object keys: `key:` -> `"key":`
    # Match word characters at the start of a key position (after { or ,)
    result = re.sub(r"(?<=[\{,\n])\s*(\w+)\s*:", lambda m: f' "{m.group(1)}":', result)

    # Remove trailing commas before } or ]
    result = re.sub(r",\s*([\]\}])", r"\1", result)

    return result


def main():
    if not os.path.isfile(BOATS_JS_PATH):
        print(f"ERROR: boats.js not found at {BOATS_JS_PATH}")
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)

    with open(BOATS_JS_PATH, encoding="utf-8") as f:
        js_content = f.read()

    # Extract and convert
    array_text = extract_boats_array(js_content)
    json_text = "[" + js_to_json(array_text) + "]"

    try:
        boats = json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"ERROR parsing converted JSON: {e}")
        # Write debug file
        debug_path = os.path.join(DATA_DIR, "_debug_conversion.json")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(json_text)
        print(f"Debug output written to {debug_path}")
        sys.exit(1)

    print(f"Parsed {len(boats)} boats from boats.js")

    # Write individual JSON files
    for boat in boats:
        slug = boat.get("slug")
        if not slug:
            print(f"  SKIP: boat without slug: {boat.get('name', '?')}")
            continue

        # Add visible: true (all existing boats are published)
        if "visible" not in boat:
            boat["visible"] = True

        out_path = os.path.join(DATA_DIR, f"{slug}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(boat, f, indent=2, ensure_ascii=False)
            f.write("\n")

        field_count = len(boat)
        print(f"  OK  {slug}.json ({field_count} fields)")

    print(f"\nMigration complete: {len(boats)} JSON files in {DATA_DIR}")


if __name__ == "__main__":
    main()
