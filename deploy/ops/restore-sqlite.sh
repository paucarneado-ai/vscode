#!/usr/bin/env bash
# restore-sqlite.sh — Restore leads database from a backup file
#
# Usage:
#   bash restore-sqlite.sh                     # interactive: lists backups, prompts for selection
#   bash restore-sqlite.sh <backup_file>       # direct: restores the specified file
#
# Safety:
#   - Stops openclaw-api before restore
#   - Creates a pre-restore snapshot
#   - Validates the backup before overwriting
#   - Restarts openclaw-api after restore
#   - Reports lead count before and after
set -euo pipefail

DB="/home/openclaw/data/leads.db"
BACKUP_DIR="/home/openclaw/backups"
SERVICE="openclaw-api"

# --- Select backup file ---
if [ -n "${1:-}" ]; then
  RESTORE_FILE="$1"
  if [ ! -f "$RESTORE_FILE" ]; then
    # Try as filename within backup dir
    RESTORE_FILE="${BACKUP_DIR}/$1"
  fi
else
  echo "Available backups:"
  echo ""
  ls -lht "${BACKUP_DIR}"/*.db 2>/dev/null || { echo "  No backups found in ${BACKUP_DIR}"; exit 1; }
  echo ""
  read -p "Enter backup filename to restore (or full path): " RESTORE_FILE
  if [ ! -f "$RESTORE_FILE" ] && [ -f "${BACKUP_DIR}/${RESTORE_FILE}" ]; then
    RESTORE_FILE="${BACKUP_DIR}/${RESTORE_FILE}"
  fi
fi

if [ ! -f "$RESTORE_FILE" ]; then
  echo "ERROR: File not found: ${RESTORE_FILE}"
  exit 1
fi

# --- Validate backup integrity ---
echo "Validating backup..."
integrity=$(sqlite3 "$RESTORE_FILE" "PRAGMA integrity_check" 2>/dev/null || echo "FAILED")
if [ "$integrity" != "ok" ]; then
  echo "ERROR: Backup integrity check failed: ${integrity}"
  exit 1
fi

backup_count=$(sqlite3 "$RESTORE_FILE" "SELECT count(*) FROM leads" 2>/dev/null || echo "ERROR")
if [ "$backup_count" = "ERROR" ]; then
  echo "ERROR: Cannot read leads table from backup"
  exit 1
fi
echo "  Backup is valid: ${backup_count} leads"

# --- Show current state ---
if [ -f "$DB" ]; then
  current_count=$(sqlite3 "$DB" "SELECT count(*) FROM leads" 2>/dev/null || echo "?")
  echo "  Current DB: ${current_count} leads"
else
  echo "  Current DB: not found (fresh restore)"
fi

# --- Confirm ---
echo ""
echo "This will:"
echo "  1. Stop ${SERVICE}"
echo "  2. Create pre-restore snapshot of current DB"
echo "  3. Replace current DB with: $(basename "$RESTORE_FILE")"
echo "  4. Restart ${SERVICE}"
echo ""
read -p "Proceed? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
  echo "Aborted."
  exit 0
fi

# --- Stop service ---
echo ""
echo "Stopping ${SERVICE}..."
systemctl stop "$SERVICE"

# --- Pre-restore snapshot ---
if [ -f "$DB" ]; then
  SNAPSHOT="${BACKUP_DIR}/pre_restore_$(date +%Y%m%d_%H%M%S).db"
  cp "$DB" "$SNAPSHOT"
  echo "Pre-restore snapshot: ${SNAPSHOT}"
fi

# --- Restore ---
echo "Restoring from: $(basename "$RESTORE_FILE")"
cp "$RESTORE_FILE" "$DB"
chown openclaw:openclaw "$DB"

# --- Verify ---
restored_count=$(sqlite3 "$DB" "SELECT count(*) FROM leads" 2>/dev/null || echo "ERROR")
echo "Restored DB: ${restored_count} leads"

# --- Restart ---
echo "Restarting ${SERVICE}..."
systemctl start "$SERVICE"
sleep 2

if systemctl is-active "$SERVICE" > /dev/null 2>&1; then
  echo ""
  echo "Restore complete. ${SERVICE} is running."
  echo "To rollback: bash restore-sqlite.sh ${SNAPSHOT:-<pre_restore_snapshot>}"
else
  echo ""
  echo "WARNING: ${SERVICE} did not start. Check: journalctl -u ${SERVICE} --no-pager -n 20"
fi
