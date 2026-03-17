def _has_user_notes(notes: str | None) -> bool:
    """Check if notes contain real user content (not just @ext: metadata)."""
    if not notes:
        return False
    for line in notes.strip().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("@ext:"):
            return True
    return False


def calculate_lead_score(source: str, notes: str | None = None) -> int:
    score = 50

    if _has_user_notes(notes):
        score += 10

    return min(score, 100)
