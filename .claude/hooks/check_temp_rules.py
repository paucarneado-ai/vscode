"""
Hook: check temporary rules on every user prompt.
Reads .claude/temporary_rules.json and injects active rules as context.
Outputs JSON for Claude Code's UserPromptSubmit hook.
"""

import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

RULES_FILE = os.path.join(os.path.dirname(__file__), "..", "temporary_rules.json")


def parse_expiration(expires_str: str, tz_name: str) -> datetime:
    """Parse expires_at as local time in the declared timezone."""
    tz = ZoneInfo(tz_name)
    naive = datetime.strptime(expires_str, "%Y-%m-%dT%H:%M:%S")
    return naive.replace(tzinfo=tz)


def main():
    if not os.path.exists(RULES_FILE):
        json.dump({"additionalContext": ""}, sys.stdout)
        return

    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        json.dump({"additionalContext": ""}, sys.stdout)
        return

    active_rules = []
    expired_rules = []

    for rule in data.get("rules", []):
        if not rule.get("enabled", True):
            continue

        expires_str = rule.get("expires_at", "")
        tz_name = rule.get("timezone", "UTC")

        try:
            expires_aware = parse_expiration(expires_str, tz_name)
        except (ValueError, KeyError):
            continue

        now_local = datetime.now(expires_aware.tzinfo)

        if now_local < expires_aware:
            remaining = expires_aware - now_local
            hours_left = remaining.total_seconds() / 3600
            active_rules.append({
                "id": rule["id"],
                "description": rule["description"],
                "hours_left": round(hours_left, 1),
                "expires_at": expires_str,
                "timezone": tz_name,
            })
        else:
            expired_rules.append(rule["id"])

    lines = []
    if active_rules:
        lines.append("=== TEMPORARY RULES ACTIVE ===")
        for r in active_rules:
            lines.append(f"[{r['id']}] {r['description']}")
            lines.append(f"  Expires: {r['expires_at']} {r['timezone']} ({r['hours_left']}h remaining)")
        lines.append("You MUST follow these rules until they expire.")
        lines.append("=== END TEMPORARY RULES ===")

    if expired_rules:
        lines.append(f"=== EXPIRED TEMPORARY RULES — NO LONGER IN EFFECT: {', '.join(expired_rules)} ===")
        lines.append("These rules have expired. Do NOT apply them. Operate under normal CLAUDE.md rules only.")

    context = "\n".join(lines)
    json.dump({"additionalContext": context}, sys.stdout)


if __name__ == "__main__":
    main()
