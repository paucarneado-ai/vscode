"""PreToolUse hook: blocks Edit/Write on protected files.

Receives tool input as JSON on stdin.
Exits 0 if allowed, exits 1 with message if blocked.
"""

import json
import sys

BLOCKED_PATTERNS = [
    "readme.md",
    "dockerfile",
    "docker-compose",
    "skills/",
]


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    normalized = file_path.replace("\\", "/").lower()

    for pattern in BLOCKED_PATTERNS:
        if pattern in normalized:
            print(
                f"BLOCKED: Cannot modify '{file_path}' — matches protected pattern '{pattern}'. "
                f"Remove this guard only with explicit user approval."
            )
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
