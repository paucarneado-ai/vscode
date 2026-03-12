from html import escape

from apps.api.schemas import LeadPackResponse


def get_rating(score: int) -> str:
    if score < 50:
        return "low"
    if score < 75:
        return "medium"
    return "high"


def build_summary(name: str, source: str, score: int, rating: str) -> str:
    return f"{name} from {source} — score {score} ({rating})"


def render_lead_pack_html(pack: LeadPackResponse) -> str:
    e = escape
    notes = e(pack.notes) if pack.notes else "—"
    return (
        "<!DOCTYPE html>"
        "<html><head><meta charset='utf-8'>"
        f"<title>Lead Pack #{pack.lead_id}</title></head><body>"
        f"<h1>Lead Pack #{pack.lead_id}</h1>"
        f"<p><strong>Name:</strong> {e(pack.name)}</p>"
        f"<p><strong>Email:</strong> {e(pack.email)}</p>"
        f"<p><strong>Source:</strong> {e(pack.source)}</p>"
        f"<p><strong>Notes:</strong> {notes}</p>"
        f"<p><strong>Score:</strong> {pack.score}</p>"
        f"<p><strong>Rating:</strong> {e(pack.rating)}</p>"
        f"<p><strong>Summary:</strong> {e(pack.summary)}</p>"
        f"<p><strong>Created at:</strong> {e(pack.created_at)}</p>"
        "</body></html>"
    )
