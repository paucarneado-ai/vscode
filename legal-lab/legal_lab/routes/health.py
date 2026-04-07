from datetime import datetime, timezone

from fastapi import APIRouter

from legal_lab.config import settings
from legal_lab.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@router.get("/health/detail")
def health_detail():
    checks = {}
    degraded = False
    try:
        db = get_db()
        checks["db"] = "ok"
        for table in ("cases", "person_entities", "timeline_events", "evidence_items",
                       "legal_issues", "strategy_notes", "analysis_artifacts",
                       "documents", "evidence_chunks",
                       "timeline_event_chunk_links", "legal_issue_chunk_links",
                       "strategy_note_chunk_links", "analysis_artifact_chunk_links",
                       "events"):
            row = db.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()
            checks[f"{table}_count"] = row["cnt"]
    except Exception as exc:
        checks["db"] = f"error: {exc}"
        degraded = True

    return {
        "status": "degraded" if degraded else "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
