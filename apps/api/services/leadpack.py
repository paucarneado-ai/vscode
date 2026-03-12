def get_rating(score: int) -> str:
    if score < 50:
        return "low"
    if score < 75:
        return "medium"
    return "high"


def build_summary(name: str, source: str, score: int, rating: str) -> str:
    return f"{name} from {source} — score {score} ({rating})"
