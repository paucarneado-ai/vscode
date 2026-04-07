"""
Status line script: shows active temporary rules count and nearest expiration.
Reads session data from stdin (unused here), outputs one line to stdout.
"""

import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

RULES_FILE = os.path.join(os.path.dirname(__file__), "..", "temporary_rules.json")


def main():
    # Consume stdin (Claude Code sends session JSON)
    try:
        sys.stdin.read()
    except Exception:
        pass

    if not os.path.exists(RULES_FILE):
        return

    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    active_count = 0
    nearest_hours = None

    for rule in data.get("rules", []):
        if not rule.get("enabled", True):
            continue
        expires_str = rule.get("expires_at", "")
        tz_name = rule.get("timezone", "UTC")
        try:
            tz = ZoneInfo(tz_name)
            naive = datetime.strptime(expires_str, "%Y-%m-%dT%H:%M:%S")
            expires_aware = naive.replace(tzinfo=tz)
        except (ValueError, KeyError):
            continue

        now_local = datetime.now(tz)
        if now_local < expires_aware:
            active_count += 1
            h = (expires_aware - now_local).total_seconds() / 3600
            if nearest_hours is None or h < nearest_hours:
                nearest_hours = h

    if active_count > 0:
        print(f"TEMP RULES: {active_count} active ({round(nearest_hours, 1)}h left)")


if __name__ == "__main__":
    main()
