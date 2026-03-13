#!/usr/bin/env bash
# restart-services.sh — Restart OpenClaw API and Caddy
# Run on the VPS: bash /home/openclaw/deploy/ops/restart-services.sh
set -euo pipefail

echo "Restarting openclaw-api..."
systemctl restart openclaw-api
sleep 1
systemctl is-active openclaw-api

echo "Restarting caddy..."
systemctl restart caddy
sleep 1
systemctl is-active caddy

echo ""
echo "Both services restarted."
