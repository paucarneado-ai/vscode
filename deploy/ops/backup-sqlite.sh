#!/usr/bin/env bash
# backup-sqlite.sh — Create a timestamped backup of the leads database
# Run on VPS: bash /home/openclaw/app/deploy/ops/backup-sqlite.sh
#
# Retention: keeps the 30 most recent backups, deletes older ones.
set -euo pipefail

DB="/home/openclaw/data/leads.db"
BACKUP_DIR="/home/openclaw/backups"
KEEP=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP="${BACKUP_DIR}/leads_${TIMESTAMP}.db"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB" ]; then
  echo "ERROR: Database not found at ${DB}"
  exit 1
fi

# Integrity check before backup
integrity=$(sqlite3 "$DB" "PRAGMA integrity_check" 2>/dev/null || echo "FAILED")
if [ "$integrity" != "ok" ]; then
  echo "WARNING: DB integrity check failed before backup: ${integrity}"
  echo "Proceeding with backup anyway (may be useful for forensics)"
fi

# Create backup using SQLite's safe .backup command
sqlite3 "$DB" ".backup ${BACKUP}"
SIZE=$(du -h "$BACKUP" | cut -f1)
COUNT=$(sqlite3 "$DB" "SELECT count(*) FROM leads" 2>/dev/null || echo "?")

echo "Backup created: ${BACKUP} (${SIZE}, ${COUNT} leads)"

# Retention: delete oldest backups beyond KEEP
backup_files=$(find "$BACKUP_DIR" -name "leads_*.db" -type f | sort -r)
total=$(echo "$backup_files" | wc -l)
if [ "$total" -gt "$KEEP" ]; then
  to_delete=$(echo "$backup_files" | tail -n +$((KEEP + 1)))
  deleted=0
  for old in $to_delete; do
    rm -f "$old"
    deleted=$((deleted + 1))
  done
  echo "Retention: deleted ${deleted} old backups (keeping ${KEEP})"
fi

echo ""
echo "Backups: $(find "$BACKUP_DIR" -name "leads_*.db" -type f | wc -l) files"
