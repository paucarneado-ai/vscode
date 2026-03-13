#!/usr/bin/env bash
# deploy-staging.sh — Sync, configure, and validate OpenClaw + Sentyacht staging
# Run from repo root (Git Bash / WSL): ./deploy/deploy-staging.sh <VPS_IP>
# Requires: root SSH access, setup-vps.sh already run, .env created
# Works with rsync (preferred) or scp (fallback for Git Bash on Windows)
set -euo pipefail

VPS_IP="${1:?Usage: $0 <VPS_IP>}"
SSH="ssh root@${VPS_IP}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Deploying staging to ${VPS_IP} ==="
echo "    Repo root: ${REPO_ROOT}"

# Detect sync tool
if command -v rsync &>/dev/null; then
  SYNC_MODE="rsync"
else
  SYNC_MODE="scp"
fi
echo "    Sync mode: ${SYNC_MODE}"

# --- Sync ---

if [ "$SYNC_MODE" = "rsync" ]; then

  echo "[1/6] Syncing backend (core reusable)..."
  rsync -avz --delete \
    --exclude '__pycache__' --exclude '*.pyc' \
    "${REPO_ROOT}/apps/" "root@${VPS_IP}:/home/openclaw/app/apps/"
  rsync -avz "${REPO_ROOT}/requirements.txt" "root@${VPS_IP}:/home/openclaw/app/"

  echo "[2/6] Syncing static site (vertical-specific)..."
  rsync -avz --delete \
    "${REPO_ROOT}/static/site/" "root@${VPS_IP}:/home/sentyacht/site/"

  echo "[3/6] Syncing deploy configs..."
  rsync -avz "${REPO_ROOT}/deploy/systemd/openclaw-api.service" "root@${VPS_IP}:/home/openclaw/deploy/systemd/"
  rsync -avz "${REPO_ROOT}/deploy/Caddyfile.sentyacht" "root@${VPS_IP}:/home/openclaw/deploy/"
  rsync -avz "${REPO_ROOT}/deploy/ops/" "root@${VPS_IP}:/home/openclaw/deploy/ops/"

else

  echo "[1/6] Copying backend (core reusable) via scp..."
  # Clean remote __pycache__ before copy
  $SSH 'rm -rf /home/openclaw/app/apps/'
  scp -r "${REPO_ROOT}/apps" "root@${VPS_IP}:/home/openclaw/app/"
  scp "${REPO_ROOT}/requirements.txt" "root@${VPS_IP}:/home/openclaw/app/"
  # Remove __pycache__ that scp copied
  $SSH 'find /home/openclaw/app/apps -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true'

  echo "[2/6] Copying static site (vertical-specific) via scp..."
  $SSH 'rm -rf /home/sentyacht/site'
  scp -r "${REPO_ROOT}/static/site" "root@${VPS_IP}:/home/sentyacht/"

  echo "[3/6] Copying deploy configs via scp..."
  $SSH 'mkdir -p /home/openclaw/deploy/systemd /home/openclaw/deploy/ops'
  scp "${REPO_ROOT}/deploy/systemd/openclaw-api.service" "root@${VPS_IP}:/home/openclaw/deploy/systemd/"
  scp "${REPO_ROOT}/deploy/Caddyfile.sentyacht" "root@${VPS_IP}:/home/openclaw/deploy/"
  scp "${REPO_ROOT}/deploy/ops/"*.sh "root@${VPS_IP}:/home/openclaw/deploy/ops/"

fi

# Fix Windows CRLF line endings in shell scripts
$SSH 'find /home/openclaw/deploy -name "*.sh" -exec sed -i "s/\r$//" {} +'

# Fix permissions
$SSH 'chown -R openclaw:openclaw /home/openclaw/ && \
  chown -R sentyacht:sentyacht /home/sentyacht/ && \
  chmod 755 /home/sentyacht /home/sentyacht/site'

# --- Install & configure ---

echo "[4/6] Installing Python dependencies..."
$SSH 'sudo -u openclaw /home/openclaw/venv/bin/pip install -q -r /home/openclaw/app/requirements.txt'

echo "[5/6] Configuring systemd and Caddy..."

# systemd
$SSH 'cp /home/openclaw/deploy/systemd/openclaw-api.service /etc/systemd/system/ && \
  systemctl daemon-reload && \
  systemctl enable openclaw-api && \
  systemctl restart openclaw-api'

# Caddy staging config (IP-only, no HTTPS) — heredoc via local stdin
$SSH 'cat > /etc/caddy/Caddyfile' << 'CADDYEOF'
:8080 {
    handle /api/* {
        uri strip_prefix /api
        reverse_proxy localhost:8000
    }

    handle {
        file_server {
            root /home/sentyacht/site
        }
    }
}
CADDYEOF
$SSH 'systemctl reload-or-restart caddy'

# --- Validate ---

echo "[6/6] Validating staging endpoints..."
echo ""

# Disable set -e for validation — we want to see all results, not abort on first failure
set +e

PASS=0
FAIL=0

check() {
  local label="$1" url="$2" expect="$3"
  local status
  status=$($SSH "curl -s -o /dev/null -w %{http_code} ${url}" 2>/dev/null)
  if [ "$status" = "$expect" ]; then
    echo "  OK  ${label} (${status})"
    PASS=$((PASS + 1))
  else
    echo "  FAIL ${label} — expected ${expect}, got ${status}"
    FAIL=$((FAIL + 1))
  fi
}

# Wait for uvicorn to start
sleep 2

check "API health"           "http://127.0.0.1:8000/health"      "200"
check "Home (/)"             "http://127.0.0.1:8080/"              "200"
check "Landing (/vender/)"   "http://127.0.0.1:8080/vender/"      "200"
check "CSS (brand.css)"      "http://127.0.0.1:8080/css/brand.css" "200"
check "API via Caddy"        "http://127.0.0.1:8080/api/health"    "200"

set -e

echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "Debug commands:"
  echo "  ssh root@${VPS_IP} 'systemctl status openclaw-api'"
  echo "  ssh root@${VPS_IP} 'systemctl status caddy'"
  echo "  ssh root@${VPS_IP} 'journalctl -u openclaw-api --no-pager -n 20'"
  exit 1
fi

echo ""
echo "Staging accessible at: http://${VPS_IP}:8080/"
echo "API accessible at:     http://${VPS_IP}:8080/api/health"
