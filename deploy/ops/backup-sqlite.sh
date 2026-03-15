#!/usr/bin/env bash
# backup-sqlite.sh — Create a timestamped backup of the leads database
# Run on the VPS: bash /home/openclaw/deploy/ops/backup-sqlite.sh
set -euo pipefail

DB="/home/openclaw/data/leads.db"
BACKUP_DIR="/home/openclaw/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP="${BACKUP_DIR}/leads_${TIMESTAMP}.db"

if [ ! -f "$DB" ]; then
  echo "ERROR: Database not found at ${DB}"
  exit 1
fi

sqlite3 "$DB" ".backup ${BACKUP}"
SIZE=$(du -h "$BACKUP" | cut -f1)
COUNT=$(sqlite3 "$DB" "SELECT count(*) FROM leads" 2>/dev/null || echo "?")

echo "Backup created: ${BACKUP} (${SIZE}, ${COUNT} leads)"

# Show existing backups
echo ""
echo "All backups:"
ls -lh "${BACKUP_DIR}/"*.db 2>/dev/null || echo "  (none)"
