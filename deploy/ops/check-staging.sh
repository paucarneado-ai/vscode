#!/usr/bin/env bash
# check-staging.sh — Operational health check
# Run on VPS: bash /home/openclaw/app/deploy/ops/check-staging.sh
set -uo pipefail

PASS=0
FAIL=0
WARN=0

ok()   { echo "  OK    $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL  $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  WARN  $1"; WARN=$((WARN + 1)); }

echo "=== OpenClaw health check ==="
echo ""

# --- Services ---
echo "Services:"
for svc in openclaw-api caddy; do
  if systemctl is-active "$svc" > /dev/null 2>&1; then
    ok "$svc"
  else
    fail "$svc ($(systemctl is-active "$svc" 2>/dev/null))"
  fi
done
echo ""

# --- Endpoints ---
echo "Endpoints:"
check_http() {
  local label="$1" url="$2" expect="${3:-200}"
  local code
  code=$(curl -s -o /dev/null -w %{http_code} --max-time 5 "$url" 2>/dev/null)
  if [ "$code" = "$expect" ]; then
    ok "$label ($code)"
  else
    fail "$label — expected $expect, got $code"
  fi
}

check_http "API direct"     "http://127.0.0.1:8000/health"
check_http "Home"           "http://127.0.0.1:8080/"
check_http "Home ES"        "http://127.0.0.1:8080/es/"
check_http "Landing"        "http://127.0.0.1:8080/es/vender-mi-barco/"
check_http "Styles"         "http://127.0.0.1:8080/styles.css"
check_http "API blocked"    "http://127.0.0.1:8080/api/health" "403"
echo ""

# --- Auth ---
echo "Auth:"
# Protected endpoint without key should fail
no_key_code=$(curl -s -o /dev/null -w %{http_code} --max-time 5 "http://127.0.0.1:8000/leads" 2>/dev/null)
if [ "$no_key_code" = "401" ]; then
  ok "protected endpoint rejects no-key (401)"
elif [ "$no_key_code" = "200" ]; then
  # Auth disabled (dev mode) — warn, not fail
  warn "protected endpoint open without key (auth disabled / dev mode)"
else
  fail "protected endpoint returned $no_key_code without key (expected 401)"
fi

# If API key is available, test authenticated access
if [ -n "${OPENCLAW_API_KEY:-}" ]; then
  key_code=$(curl -s -o /dev/null -w %{http_code} --max-time 5 \
    -H "X-API-Key: ${OPENCLAW_API_KEY}" "http://127.0.0.1:8000/leads" 2>/dev/null)
  if [ "$key_code" = "200" ]; then
    ok "authenticated access works (200)"
  else
    fail "authenticated access returned $key_code (expected 200)"
  fi

  bad_code=$(curl -s -o /dev/null -w %{http_code} --max-time 5 \
    -H "X-API-Key: INVALID_KEY_12345" "http://127.0.0.1:8000/leads" 2>/dev/null)
  if [ "$bad_code" = "403" ]; then
    ok "invalid key rejected (403)"
  else
    fail "invalid key returned $bad_code (expected 403)"
  fi
else
  warn "OPENCLAW_API_KEY not set — skipping authenticated checks"
fi
echo ""

# --- Database ---
echo "Database:"
DB="/home/openclaw/data/leads.db"
if [ -f "$DB" ]; then
  size=$(du -h "$DB" | cut -f1)
  count=$(sqlite3 "$DB" "SELECT count(*) FROM leads" 2>/dev/null || echo "ERROR")
  if [ "$count" = "ERROR" ]; then
    fail "leads table unreadable"
  else
    ok "$size, $count leads"
  fi
  integrity=$(sqlite3 "$DB" "PRAGMA integrity_check" 2>/dev/null || echo "FAILED")
  if [ "$integrity" = "ok" ]; then
    ok "integrity check passed"
  else
    fail "integrity check: $integrity"
  fi
else
  fail "DB not found at $DB"
fi
echo ""

# --- Backups ---
echo "Backups:"
BACKUP_DIR="/home/openclaw/backups"
if [ -d "$BACKUP_DIR" ]; then
  backup_count=$(find "$BACKUP_DIR" -name "leads_*.db" -type f 2>/dev/null | wc -l)
  latest=$(find "$BACKUP_DIR" -name "leads_*.db" -type f -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
  if [ -n "$latest" ]; then
    latest_age_hours=$(( ($(date +%s) - $(stat -c %Y "$latest" 2>/dev/null || echo 0)) / 3600 ))
    ok "$backup_count files, latest: $(basename "$latest") (${latest_age_hours}h ago)"
    if [ "$latest_age_hours" -gt 48 ]; then
      warn "latest backup is ${latest_age_hours}h old (>48h)"
    fi
  else
    warn "backup directory exists but empty"
  fi
else
  warn "backup directory not found"
fi
echo ""

# --- Cron ---
echo "Cron:"
if crontab -l 2>/dev/null | grep -q "backup-sqlite"; then
  cron_line=$(crontab -l 2>/dev/null | grep "backup-sqlite")
  ok "backup cron installed: $cron_line"
else
  warn "backup cron not found in root crontab"
fi
echo ""

# --- Disk ---
echo "Disk:"
data_disk=$(df -h /home/openclaw/data 2>/dev/null | tail -1 | awk '{print $5}')
if [ -n "$data_disk" ]; then
  pct=${data_disk%\%}
  if [ "$pct" -lt 85 ]; then
    ok "data partition: ${data_disk} used"
  elif [ "$pct" -lt 95 ]; then
    warn "data partition: ${data_disk} used"
  else
    fail "data partition: ${data_disk} used — critically low"
  fi
fi
echo ""

# --- Summary ---
echo "=== $PASS OK, $FAIL FAIL, $WARN WARN ==="
[ "$FAIL" -eq 0 ]
