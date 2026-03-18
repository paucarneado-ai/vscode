"""CLI for reviewing pathway_discovery review queue items.

Usage:
    python -m apps.pathway_discovery.review_cli list
    python -m apps.pathway_discovery.review_cli history
    python -m apps.pathway_discovery.review_cli show <fingerprint>
    python -m apps.pathway_discovery.review_cli set <fingerprint> --status <status> [--note "..."] [--reason "..."]
"""

import argparse
import json
import os
import sys
from datetime import datetime

VALID_STATUSES = {"unreviewed", "keep", "monitor", "schedule", "resolved"}


def _report_path(repo_root: str | None = None) -> str:
    if repo_root is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(repo_root, "reports", "pathway_audit_latest.json")


def _load_report(path: str) -> dict:
    if not os.path.isfile(path):
        print(f"Error: no audit report found at {path}", file=sys.stderr)
        print("Run: python -m apps.pathway_discovery.reporter", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_report(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _get_queue_state(data: dict) -> dict[str, dict]:
    return data.get("review_queue_state", {})


def cmd_list(data: dict) -> None:
    """Show active review queue items."""
    state = _get_queue_state(data)
    active = {fp: e for fp, e in state.items()
              if not e.get("inactive") and e.get("operator_status", "unreviewed") != "resolved"}

    if not active:
        print("Review queue is empty.")
        return

    # Enrich with recommendation data if available
    rec_map = {}
    for r in data.get("recommendations", []):
        rec_map[r.get("stable_fingerprint", "")] = r

    print(f"Active review queue: {len(active)} items\n")
    for fp, entry in sorted(active.items()):
        rec = rec_map.get(fp, {})
        print(f"  {fp[:12]}")
        print(f"    bucket:  {entry.get('last_bucket', rec.get('review_bucket', '?'))}")
        print(f"    status:  {entry.get('operator_status', 'unreviewed')}")
        if rec.get("why_now"):
            print(f"    why_now: {rec['why_now']}")
        if rec.get("intervention_hint"):
            print(f"    hint:    {rec['intervention_hint']}")
        if entry.get("operator_note"):
            print(f"    note:    {entry['operator_note']}")
        print()


def cmd_history(data: dict) -> None:
    """Show decision log: reviewed, resolved, or inactive items."""
    state = _get_queue_state(data)
    historical = {fp: e for fp, e in state.items()
                  if e.get("inactive") or e.get("operator_status", "unreviewed") != "unreviewed"}

    if not historical:
        print("No decision history.")
        return

    print(f"Decision history: {len(historical)} entries\n")
    for fp, entry in sorted(historical.items()):
        inactive_tag = " [inactive]" if entry.get("inactive") else ""
        print(f"  {fp[:12]}{inactive_tag}")
        print(f"    status:  {entry.get('operator_status', '?')}")
        if entry.get("decision_reason"):
            print(f"    reason:  {entry['decision_reason']}")
        if entry.get("operator_note"):
            print(f"    note:    {entry['operator_note']}")
        if entry.get("reviewed_at"):
            print(f"    reviewed: {entry['reviewed_at']}")
        if entry.get("last_description"):
            print(f"    desc:    {entry['last_description'][:80]}")
        print()


def cmd_show(data: dict, fingerprint: str) -> None:
    """Show full stored state for one item."""
    state = _get_queue_state(data)

    # Match by prefix
    matches = [(fp, e) for fp, e in state.items() if fp.startswith(fingerprint)]
    if not matches:
        print(f"Error: fingerprint '{fingerprint}' not found in review queue.", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print(f"Error: ambiguous fingerprint '{fingerprint}', matches: {[m[0][:12] for m in matches]}", file=sys.stderr)
        sys.exit(1)

    fp, entry = matches[0]
    print(f"Fingerprint: {fp}")
    for k, v in sorted(entry.items()):
        print(f"  {k}: {v}")

    # Show recommendation data if available
    for r in data.get("recommendations", []):
        if r.get("stable_fingerprint") == fp:
            print(f"\n  -- From current audit --")
            for k in ("type", "score", "review_bucket", "watchlist_age",
                      "watchlist_severity_score", "escalated_watchlist",
                      "debt_status", "debt_age", "why_now", "intervention_hint"):
                if k in r:
                    print(f"  {k}: {r[k]}")
            if r.get("modules"):
                print(f"  modules: {', '.join(r['modules'])}")
            break


def cmd_set(data: dict, path: str, fingerprint: str, status: str,
            note: str | None = None, reason: str | None = None) -> None:
    """Update operator review state for an item."""
    if status not in VALID_STATUSES:
        print(f"Error: invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}", file=sys.stderr)
        sys.exit(1)

    state = _get_queue_state(data)

    # Match by prefix
    matches = [fp for fp in state if fp.startswith(fingerprint)]
    if not matches:
        print(f"Error: fingerprint '{fingerprint}' not found in review queue.", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print(f"Error: ambiguous fingerprint '{fingerprint}'.", file=sys.stderr)
        sys.exit(1)

    fp = matches[0]
    entry = state[fp]
    old_status = entry.get("operator_status", "unreviewed")

    entry["operator_status"] = status
    if note is not None:
        entry["operator_note"] = note
    if reason is not None:
        entry["decision_reason"] = reason

    # Auto-set reviewed_at when transitioning away from unreviewed
    if old_status == "unreviewed" and status != "unreviewed":
        entry["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    _save_report(path, data)
    print(f"Updated {fp[:12]}: status={status}")
    if note:
        print(f"  note: {note}")
    if reason:
        print(f"  reason: {reason}")
    if entry.get("reviewed_at") and old_status == "unreviewed":
        print(f"  reviewed_at: {entry['reviewed_at']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Review pathway_discovery queue items")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="Show active review queue")
    sub.add_parser("history", help="Show decision log / inactive items")

    show_p = sub.add_parser("show", help="Show full state for one item")
    show_p.add_argument("fingerprint", help="Fingerprint (or prefix)")

    set_p = sub.add_parser("set", help="Update review status")
    set_p.add_argument("fingerprint", help="Fingerprint (or prefix)")
    set_p.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    set_p.add_argument("--note", default=None, help="Operator note")
    set_p.add_argument("--reason", default=None, help="Decision reason")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    path = _report_path()
    data = _load_report(path)

    if args.command == "list":
        cmd_list(data)
    elif args.command == "history":
        cmd_history(data)
    elif args.command == "show":
        cmd_show(data, args.fingerprint)
    elif args.command == "set":
        cmd_set(data, path, args.fingerprint, args.status,
                note=args.note, reason=args.reason)


if __name__ == "__main__":
    main()
