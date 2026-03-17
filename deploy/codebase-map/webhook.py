"""Lightweight webhook receiver for GitHub push events.

Listens on port 9000. When a POST arrives at /webhook, it pulls the
latest code and regenerates the codebase map.

No dependencies beyond Python stdlib.
"""

import json
import os
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

REPO_DIR = "/app/repo"
REPO_BRANCH = os.environ.get("REPO_BRANCH", "main")


def regenerate():
    """Pull latest code and regenerate the map."""
    print("[webhook] Pulling latest code...")
    try:
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=REPO_DIR, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "reset", "--hard", f"origin/{REPO_BRANCH}"],
            cwd=REPO_DIR, check=True, capture_output=True,
        )

        # Copy updated source files
        for src, dst in [
            ("scripts/generate_map.py", "/app/scripts/generate_map.py"),
            ("static/codebase-map-template.html", "/app/static/codebase-map-template.html"),
        ]:
            full = os.path.join(REPO_DIR, src)
            if os.path.exists(full):
                with open(full, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(dst, "w", encoding="utf-8") as f:
                    f.write(content)

        print("[webhook] Regenerating map...")
        result = subprocess.run(
            ["python", "/app/scripts/generate_map.py"],
            capture_output=True, text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"[webhook] Generator error: {result.stderr}")
            return

        # Copy to nginx serve dir
        os.makedirs("/var/www/html", exist_ok=True)
        with open("/app/static/codebase-map.html", "r", encoding="utf-8") as f:
            html = f.read()
        with open("/var/www/html/index.html", "w", encoding="utf-8") as f:
            f.write(html)

        print("[webhook] Map updated successfully!")

    except Exception as e:
        print(f"[webhook] Error: {e}")


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/webhook":
            content_length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(content_length)  # consume body

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"regenerating"}')

            # Run regeneration in background thread
            threading.Thread(target=regenerate, daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/webhook/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        print(f"[webhook] {args[0]}")


def main():
    server = HTTPServer(("0.0.0.0", 9000), WebhookHandler)
    print("[webhook] Listening on port 9000")
    server.serve_forever()


if __name__ == "__main__":
    main()
