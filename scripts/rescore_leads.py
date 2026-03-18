"""One-off script to recalculate scores for existing leads.

Usage:
    DRY RUN (default):  python scripts/rescore_leads.py
    APPLY:              python scripts/rescore_leads.py --apply

Requires DATABASE_PATH env var pointing to the SQLite file.
"""

import os
import sys

# Add project root to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlite3
from apps.api.services.scoring import calculate_lead_score


def main():
    apply = "--apply" in sys.argv
    db_path = os.environ.get("DATABASE_PATH", "openclaw.db")

    if not os.path.exists(db_path):
        print(f"ERROR: database not found at {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, name, source, notes, score FROM leads ORDER BY id").fetchall()

    if not rows:
        print("No leads found.")
        return

    changes = []
    for row in rows:
        old_score = row["score"]
        new_score = calculate_lead_score(row["source"], row["notes"])
        if old_score != new_score:
            changes.append((row["id"], row["name"], row["source"], old_score, new_score))

    print(f"Total leads: {len(rows)}")
    print(f"Would change: {len(changes)}")
    print(f"No change: {len(rows) - len(changes)}")
    print()

    if changes:
        print(f"{'ID':>4}  {'Name':<30}  {'Old':>4} → {'New':>4}  Delta")
        print("-" * 65)
        for lead_id, name, source, old, new in changes:
            delta = new - old
            sign = "+" if delta > 0 else ""
            print(f"{lead_id:>4}  {name[:30]:<30}  {old:>4} → {new:>4}  {sign}{delta}")

    if not apply:
        print(f"\nDRY RUN — no changes written. Run with --apply to execute.")
        return

    print(f"\nApplying {len(changes)} updates...")
    for lead_id, name, source, old, new in changes:
        conn.execute("UPDATE leads SET score = ? WHERE id = ?", (new, lead_id))
    conn.commit()
    print("Done. Scores updated.")

    conn.close()


if __name__ == "__main__":
    main()
