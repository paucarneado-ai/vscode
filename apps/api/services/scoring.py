"""Lead scoring engine.

Deterministic scoring based on available data signals.
No ML, no external services, no guesswork.

Score range: 0-100
Breakdown:
  Base:                    20
  Source quality:        +5-10
  Has structured data:    +5
  Phone provided:        +10
  High-value boat type:  +10
  Eslora >= 10m:         +10
  Price indicated:       +15
  Detail fields filled:  +5 each (max +20)
  Free-text message:      +5

Max theoretical: 20+10+5+10+10+10+15+20+5 = 105, capped at 100
"""

import re

# Boat types that signal higher-value operations
HIGH_VALUE_TYPES = {"yate a motor", "catamarán a motor", "catamarán de vela", "velero"}

# Legacy form values that map to high-value types
HIGH_VALUE_INTERES = {"venta-barco-motor", "venta-velero", "compra-embarcacion"}

# Sources that signal direct, intentional engagement
HIGH_QUALITY_SOURCES = {"web:sentyacht-vender", "web:sentyacht"}
MEDIUM_QUALITY_SOURCES = {"webhook:landing-barcos-venta"}

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
    """Score a lead 0-100 based on source and structured notes content."""
    score = 20

    # --- Source quality ---
    source_lower = source.lower()
    if source_lower in HIGH_QUALITY_SOURCES:
        score += 10
    elif source_lower in MEDIUM_QUALITY_SOURCES:
        score += 7
    elif source_lower == "test":
        score += 5
    # Unknown/other sources: +0

    if not notes or not notes.strip():
        return score

    # --- Has structured data at all ---
    score += 5

    # --- Phone provided (strong intent: willing to be called back) ---
    phone = _parse_notes_field(notes, "Teléfono:") or _parse_notes_field(notes, "Telefono:")
    if phone and len(phone.strip()) >= 6:
        score += 10

    # --- High-value boat type ---
    interes = _parse_notes_field(notes, "Interés:") or _parse_notes_field(notes, "Tipo:")
    if interes:
        boat_type = interes.split("—")[0].strip().lower()
        if boat_type in HIGH_VALUE_TYPES or boat_type in HIGH_VALUE_INTERES:
            score += 10

    # --- Eslora >= 10m (meaningful vessel size) ---
    eslora = _parse_eslora_meters(notes)
    if eslora is not None and eslora >= 10:
        score += 10

    # --- Price indicated (strongest commercial signal) ---
    price = _parse_notes_field(notes, "Precio orientativo:")
    if price:
        score += 15

    # --- Detail fields filled (serious intent) ---
    details_filled = sum(1 for signal in DETAIL_SIGNALS if _parse_notes_field(notes, signal))
    score += min(details_filled, 4) * 5

    # --- Free-text message (effort indicator) ---
    mensaje = _parse_notes_field(notes, "Mensaje:")
    if mensaje and len(mensaje.strip()) >= 10:
        score += 5

    return min(score, 100)
