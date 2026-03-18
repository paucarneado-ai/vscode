import re


# Boat types that signal higher-value operations
HIGH_VALUE_TYPES = {"yate a motor", "catamarán a motor", "catamarán de vela", "velero"}

# Optional detail fields that signal serious intent when filled
DETAIL_SIGNALS = ["Marca/modelo:", "Año:", "Puerto:", "Precio orientativo:"]


def _parse_notes_field(notes: str, prefix: str) -> str | None:
    """Extract the value after a prefix line in structured notes."""
    for line in notes.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith(prefix.lower()):
            value = stripped[len(prefix):].strip()
            return value if value else None
    return None


def _parse_eslora_meters(notes: str) -> float | None:
    """Try to extract eslora in meters from notes."""
    raw = _parse_notes_field(notes, "Interés:") or _parse_notes_field(notes, "Eslora:")
    if not raw:
        return None
    # Extract numeric part: "Velero — 12m" → look for number
    # Handle "Interés: Yate a motor — 18" pattern
    parts = raw.split("—")
    text = parts[-1].strip() if len(parts) > 1 else raw
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    value = float(match.group(1))
    if "pie" in text.lower() or "ft" in text.lower() or "feet" in text.lower():
        value *= 0.3048
    return value


def calculate_lead_score(source: str, notes: str | None = None) -> int:
    """Score a lead 0-100 based on source and structured notes content.

    Scoring breakdown:
      Base:                30
      Has notes:          +10
      High-value boat:    +10
      Eslora >= 10m:      +10
      Price indicated:    +15
      Each detail field:  + 5 (up to 4 = +20)
      Source "test":      + 5

    Max theoretical: 30+10+10+10+15+20+5 = 100
    """
    score = 30

    if source.lower() == "test":
        score += 5

    if not notes or not notes.strip():
        return score

    score += 10  # has notes at all

    # High-value boat type
    interes = _parse_notes_field(notes, "Interés:") or _parse_notes_field(notes, "Tipo:")
    if interes:
        # Extract boat type before the dash (e.g., "Yate a motor — 18" → "Yate a motor")
        boat_type = interes.split("—")[0].strip().lower()
        if boat_type in HIGH_VALUE_TYPES:
            score += 10

    # Eslora >= 10m signals meaningful vessel
    eslora = _parse_eslora_meters(notes)
    if eslora is not None and eslora >= 10:
        score += 10

    # Price indicated = strong commercial signal
    price = _parse_notes_field(notes, "Precio orientativo:")
    if price:
        score += 15

    # Count detail fields filled (serious intent)
    details_filled = sum(1 for signal in DETAIL_SIGNALS if _parse_notes_field(notes, signal))
    score += min(details_filled, 4) * 5

    return min(score, 100)