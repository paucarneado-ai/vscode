#!/usr/bin/env bash
# verify-backup.sh — Validate that a backup is actually recoverable
#
# Usage:
#   bash verify-backup.sh                   # verifies the latest backup
#   bash verify-backup.sh <backup_file>     # verifies a specific file
#
# Does NOT touch the live database.
# Opens the backup in a temp location, checks integrity, reads leads, compares count.
set -euo pipefail

BACKUP_DIR="/home/openclaw/backups"
DB="/home/openclaw/data/leads.db"

# --- Select backup ---
if [ -n "${1:-}" ]; then
  BACKUP="$1"
  [ ! -f "$BACKUP" ] && BACKUP="${BACKUP_DIR}/$1"
else
  BACKUP=$(find "$BACKUP_DIR" -name "leads_*.db" -type f -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
  if [ -z "$BACKUP" ]; then
    echo "ERROR: No backups found in ${BACKUP_DIR}"
    exit 1
  fi
  echo "Verifying latest backup: $(basename "$BACKUP")"
fi

if [ ! -f "$BACKUP" ]; then
  echo "ERROR: File not found: ${BACKUP}"
  exit 1
fi

PASS=0
FAIL=0

ok()   { echo "  OK    $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL  $1"; FAIL=$((FAIL + 1)); }

echo ""

# --- File checks ---
backup_size=$(du -h "$BACKUP" | cut -f1)
ok "file exists ($backup_size)"

# --- Integrity ---
integrity=$(sqlite3 "$BACKUP" "PRAGMA integrity_check" 2>/dev/null || echo "FAILED")
if [ "$integrity" = "ok" ]; then
  ok "integrity check passed"
else
  fail "integrity check: $integrity"
fi

# --- Schema ---
has_leads=$(sqlite3 "$BACKUP" "SELECT name FROM sqlite_master WHERE type='table' AND name='leads'" 2>/dev/null || echo "")
if [ "$has_leads" = "leads" ]; then
  ok "leads table exists"
else
  fail "leads table missing"
  echo ""
  echo "=== $PASS OK, $FAIL FAIL ==="
  exit 1
fi

# --- Data readable ---
backup_count=$(sqlite3 "$BACKUP" "SELECT count(*) FROM leads" 2>/dev/null || echo "ERROR")
if [ "$backup_count" != "ERROR" ]; then
  ok "leads readable: $backup_count rows"
else
  fail "cannot read leads table"
fi

# --- Sample query ---
sample=$(sqlite3 "$BACKUP" "SELECT id, email, score FROM leads ORDER BY id DESC LIMIT 1" 2>/dev/null || echo "ERROR")
if [ "$sample" != "ERROR" ] && [ -n "$sample" ]; then
  ok "sample query works: $sample"
else
  if [ "$backup_count" = "0" ]; then
    ok "sample query: empty table (valid)"
  else
    fail "sample query failed"
  fi
fi

# --- Compare with live DB ---
if [ -f "$DB" ]; then
  live_count=$(sqlite3 "$DB" "SELECT count(*) FROM leads" 2>/dev/null || echo "?")
  echo ""
  echo "  Comparison: backup=${backup_count} leads, live=${live_count} leads"
  if [ "$backup_count" != "ERROR" ] && [ "$live_count" != "?" ]; then
    diff=$((live_count - backup_count))
    if [ "$diff" -ge 0 ]; then
      echo "  Delta: live has ${diff} more leads than backup (expected if backup is older)"
    else
      echo "  Delta: backup has $((-diff)) more leads than live (unexpected — investigate)"
    fi
  fi
fi

echo ""
echo "=== $PASS OK, $FAIL FAIL ==="
[ "$FAIL" -eq 0 ]
