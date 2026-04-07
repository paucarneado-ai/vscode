#!/bin/bash
set -e

REPO_URL="${REPO_URL:-}"
REPO_BRANCH="${REPO_BRANCH:-main}"
REPO_DIR="/app/repo"

echo "=== OpenClaw Codebase Map ==="

# Clone repo if URL is set
if [ -n "$REPO_URL" ]; then
    echo "Cloning $REPO_URL ($REPO_BRANCH)..."
    if [ -d "$REPO_DIR/.git" ]; then
        cd "$REPO_DIR" && git fetch origin && git reset --hard "origin/$REPO_BRANCH"
    else
        git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"
    fi

    # Copy latest source files for the generator
    cp "$REPO_DIR/scripts/generate_map.py" /app/scripts/generate_map.py 2>/dev/null || true
    cp "$REPO_DIR/static/codebase-map-template.html" /app/static/codebase-map-template.html 2>/dev/null || true

    # Point generator at the cloned repo
    export PROJECT_ROOT="$REPO_DIR"
fi

# Generate the map
echo "Generating codebase map..."
cd /app
python /app/scripts/generate_map.py

# Copy output to nginx serve directory
mkdir -p /var/www/html
cp /app/static/codebase-map.html /var/www/html/index.html

echo "Map ready at http://localhost:80"

# Start webhook server in background (listens on port 9000)
python /app/webhook.py &

# Start nginx in foreground
nginx -g 'daemon off;'
