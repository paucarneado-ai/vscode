def determine_next_action(score: int, notes: str | None) -> str:
    has_notes = bool(notes and notes.strip())

    if score >= 60:
        return "send_to_client"
    if score >= 40:
        return "review_manually" if has_notes else "request_more_info"
    return "enrich_first" if has_notes else "discard"


def should_alert(score: int) -> bool:
    return score >= 60


ACTION_PRIORITY: list[str] = ["send_to_client", "review_manually", "request_more_info", "enrich_first"]

ACTION_INSTRUCTIONS: dict[str, str] = {
    "send_to_client": "Contactar al propietario. Lead cualificado con datos suficientes para primera conversacion.",
    "review_manually": "Revisar datos antes de contactar. Hay informacion pero falta valorar si merece seguimiento directo.",
    "request_more_info": "Pedir mas datos. El lead tiene poco detalle para evaluar interes real.",
    "enrich_first": "Buscar informacion adicional. Datos insuficientes para actuar.",
    "discard": "Descartar. Sin datos utiles.",
}


def get_instruction(next_action: str) -> str:
    return ACTION_INSTRUCTIONS.get(next_action, f"Unknown action: {next_action}")


def build_priority_reason(score: int, notes: str | None, source: str) -> str:
    """Build a short, deterministic explanation of why this lead has its current priority.

    Returns a concise string an operator can scan in a list view.
    """
    parts: list[str] = []

    # Source signal
    src = source.lower()
    if src.startswith("web:sentyacht"):
        parts.append("web directa")
    elif "meta" in src:
        parts.append("Meta Ads")
    elif src.startswith("webhook:"):
        parts.append("webhook")

    if not notes or not notes.strip():
        parts.append("sin datos")
        return ", ".join(parts) if parts else "sin informacion"

    # Key signals from notes
    lines_lower = notes.lower()
    if "teléfono:" in lines_lower or "telefono:" in lines_lower:
        parts.append("tiene telefono")
    if any(t in lines_lower for t in ("yate", "velero", "catamarán", "catamaran")):
        parts.append("embarcacion de valor")
    if "precio" in lines_lower:
        parts.append("precio indicado")
    if "eslora:" in lines_lower or "— " in notes:
        # Check for meaningful length
        import re
        match = re.search(r"(\d+)", notes.split("—")[-1] if "—" in notes else "")
        if match and int(match.group(1)) >= 10:
            parts.append("eslora >= 10m")

    if not parts:
        parts.append("datos basicos")

    return ", ".join(parts)
