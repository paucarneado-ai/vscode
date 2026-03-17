"""All-in-one server: serves the codebase map HTML + handles GitHub webhook.

- GET /           → serves the codebase map
- POST /webhook   → pulls latest code, regenerates map
- GET /health     → health check
"""

import os
import subprocess
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PORT = 80
REPO_DIR = "/app/repo"
REPO_BRANCH = os.environ.get("REPO_BRANCH", "main")
MAP_FILE = "/app/static/codebase-map.html"
SERVE_DIR = "/app/www"


def regenerate():
    """Pull latest code and regenerate the map."""
    print("[regen] Pulling latest code...")
    try:
        subprocess.run(["git", "fetch", "origin"], cwd=REPO_DIR, check=True, capture_output=True)
        subprocess.run(["git", "reset", "--hard", f"origin/{REPO_BRANCH}"], cwd=REPO_DIR, check=True, capture_output=True)

        # Update generator files from repo
        for src, dst in [
            ("scripts/generate_map.py", "/app/generate_map.py"),
            ("static/codebase-map-template.html", "/app/codebase-map-template.html"),
        ]:
            full = os.path.join(REPO_DIR, src)
            if os.path.exists(full):
                with open(full, "r", encoding="utf-8") as f:
                    data = f.read()
                with open(dst, "w", encoding="utf-8") as f:
                    f.write(data)

        print("[regen] Running generator...")
        result = subprocess.run(["python", "/app/generate_map.py"], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(f"[regen] Error: {result.stderr}")
            return

        # Copy to serve directory
        if os.path.exists(MAP_FILE):
            os.makedirs(SERVE_DIR, exist_ok=True)
            with open(MAP_FILE, "r", encoding="utf-8") as f:
                html = f.read()
            with open(os.path.join(SERVE_DIR, "index.html"), "w", encoding="utf-8") as f:
                f.write(html)
            print("[regen] Map updated!")
        else:
            print(f"[regen] Warning: {MAP_FILE} not found")

    except Exception as e:
        print(f"[regen] Error: {e}")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    def do_POST(self):
        if self.path == "/webhook":
            # Read and discard body
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"regenerating"}')

            threading.Thread(target=regenerate, daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        elif self.path == "/webhook":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Webhook endpoint ready. Send POST to trigger regeneration.")
        else:
            # Serve static files (index.html)
            if self.path == "/":
                self.path = "/index.html"
            super().do_GET()

    def log_message(self, format, *args):
        print(f"[http] {args[0]}")


def main():
    # Initial setup: ensure serve directory has the map
    os.makedirs(SERVE_DIR, exist_ok=True)

    if os.path.exists(MAP_FILE):
        with open(MAP_FILE, "r", encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(SERVE_DIR, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[init] Serving existing map")
    else:
        # Generate for the first time
        print("[init] No map found, generating...")
        regenerate()

    if not os.path.exists(os.path.join(SERVE_DIR, "index.html")):
        # Fallback: create a placeholder
        with open(os.path.join(SERVE_DIR, "index.html"), "w") as f:
            f.write("<h1>OpenClaw Codebase Map</h1><p>Generating... refresh in a moment.</p>")

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[server] Listening on port {PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
