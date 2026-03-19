"""DEPRECATED — wrapper que delega a build_site.py.

Este script existía para regenerar solo las galerías HTML desde manifest.json.
Desde marzo 2026, build_site.py genera TODO el sitio (boats.js + 24 páginas HTML)
desde la fuente de verdad en data/boats/*.json + manifest.json.

Este archivo se mantiene como wrapper por compatibilidad con scripts y documentación
que aún lo referencien. Toda la lógica real está en build_site.py.

Usage: python scripts/integrate_galleries.py
       (equivale a: python scripts/build_site.py)
"""

import os
import subprocess
import sys


def main():
    print("AVISO: integrate_galleries.py está deprecated.", file=sys.stderr)
    print("       Delegando a build_site.py...\n", file=sys.stderr)
    script = os.path.join(os.path.dirname(__file__), "build_site.py")
    result = subprocess.run([sys.executable, script])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
