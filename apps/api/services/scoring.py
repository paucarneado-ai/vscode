def calculate_lead_score(source: str, notes: str | None = None) -> int:
    score = 50

    if source.lower() == "test":
        score += 10

    if notes and notes.strip():
        score += 10

    return min(score, 100)