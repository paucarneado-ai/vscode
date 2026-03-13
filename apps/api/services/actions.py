def determine_next_action(score: int, notes: str | None) -> str:
    has_notes = bool(notes and notes.strip())

    if score >= 60:
        return "send_to_client"
    if score >= 40:
        return "review_manually" if has_notes else "request_more_info"
    return "enrich_first" if has_notes else "discard"


def should_alert(score: int) -> bool:
    return score >= 60


ACTION_INSTRUCTIONS: dict[str, str] = {
    "send_to_client": "Send lead to client for prioritization",
    "review_manually": "Review lead manually",
    "request_more_info": "Request more information from lead",
    "enrich_first": "Enrich lead data before further action",
    "discard": "Discard lead — insufficient data",
}


def get_instruction(next_action: str) -> str:
    return ACTION_INSTRUCTIONS.get(next_action, f"Unknown action: {next_action}")
