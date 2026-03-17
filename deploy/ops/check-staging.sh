#!/usr/bin/env bash
# check-staging.sh — Quick health check of staging services
# Run on the VPS: bash /home/openclaw/deploy/ops/check-staging.sh
set -uo pipefail

echo "=== Staging health check ==="
echo ""

# Services
echo "Services:"
for svc in openclaw-api caddy; do
  status=$(systemctl is-active "$svc" 2>/dev/null)
  if [ "$status" = "active" ]; then
    echo "  OK  ${svc} (${status})"
  else
    echo "  FAIL ${svc} (${status})"
  fi
done
echo ""

# Endpoints
echo "Endpoints:"
PASS=0
FAIL=0

check() {
  local label="$1" url="$2"
  local code
  code=$(curl -s -o /dev/null -w %{http_code} "$url" 2>/dev/null)
  if [ "$code" = "200" ]; then
    echo "  OK  ${label} (${code})"
    PASS=$((PASS + 1))
  else
    echo "  FAIL ${label} (${code})"
    FAIL=$((FAIL + 1))
  fi
}

check "API direct"       "http://127.0.0.1:8000/health"
check "Home"             "http://127.0.0.1:8080/"
check "Landing"          "http://127.0.0.1:8080/vender/"
check "CSS"              "http://127.0.0.1:8080/css/brand.css"
check "API via Caddy"    "http://127.0.0.1:8080/api/health"

echo ""

# DB
if [ -f /home/openclaw/data/leads.db ]; then
  count=$(sqlite3 /home/openclaw/data/leads.db "SELECT count(*) FROM leads" 2>/dev/null || echo "ERROR")
  size=$(du -h /home/openclaw/data/leads.db | cut -f1)
  echo "Database: ${size}, ${count} leads"
else
  echo "Database: NOT FOUND"
fi

echo ""
echo "=== ${PASS} OK, ${FAIL} FAIL ==="
