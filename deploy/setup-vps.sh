#!/usr/bin/env bash
# setup-vps.sh — First-time VPS setup for OpenClaw + Sentyacht staging
# Run from local machine (WSL/Git Bash): ./deploy/setup-vps.sh <VPS_IP>
# Requires: root SSH access to the VPS
# Idempotent: safe to re-run
set -euo pipefail

VPS_IP="${1:?Usage: $0 <VPS_IP>}"
SSH="ssh root@${VPS_IP}"

echo "=== Setup VPS at ${VPS_IP} ==="

echo "[1/5] Installing system packages..."
$SSH 'apt update && apt install -y python3 python3-venv python3-pip sqlite3 \
  debian-keyring debian-archive-keyring apt-transport-https'

echo "[2/5] Installing Caddy..."
$SSH 'curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/gpg.key" | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>/dev/null && \
  curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt" | tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null && \
  apt update && apt install -y caddy'

echo "[3/5] Creating users..."
$SSH 'id openclaw &>/dev/null || useradd -m -s /bin/bash openclaw'
$SSH 'id sentyacht &>/dev/null || useradd -m -s /bin/bash sentyacht'

echo "[4/5] Creating directory structure..."
$SSH 'sudo -u openclaw mkdir -p /home/openclaw/app /home/openclaw/data /home/openclaw/backups /home/openclaw/deploy'
$SSH 'sudo -u sentyacht mkdir -p /home/sentyacht/site'

echo "[5/5] Creating Python virtualenv..."
$SSH 'test -d /home/openclaw/venv || sudo -u openclaw python3 -m venv /home/openclaw/venv'

echo ""
echo "=== VPS setup complete ==="
echo ""
echo "MANUAL STEP REQUIRED: Create .env file on the VPS:"
echo "  ssh root@${VPS_IP}"
echo "  cat > /home/openclaw/.env << 'EOF'"
echo "  DATABASE_PATH=/home/openclaw/data/leads.db"
echo "  EOF"
echo "  chown openclaw:openclaw /home/openclaw/.env"
echo ""
echo "Then run: ./deploy/deploy-staging.sh ${VPS_IP}"
