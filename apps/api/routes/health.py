from datetime import datetime, timezone

from fastapi import APIRouter

from apps.api.config import settings
from apps.api.db import get_db


router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
    }


@router.get("/routes")
def list_routes() -> list[str]:
    return [
        "/health",
        "/health/detail",
        "/routes",
        "/leads",
        "/leads/ingest",
        "/leads/external",
        "/leads/webhook/{provider}",
        "/leads/webhook/{provider}/batch",
        "/leads/sources",
        "/leads/summary",
        "/leads/export.csv",
        "/leads/actionable",
        "/leads/actionable/worklist",
        "/leads/{lead_id}",
        "/leads/{lead_id}/pack",
        "/leads/{lead_id}/pack/html",
        "/leads/{lead_id}/pack.txt",
        "/leads/{lead_id}/operational",
        "/leads/{lead_id}/delivery",
    ]


@router.get("/health/detail")
def health_detail() -> dict:
    db_status = "ok"
    lead_count = 0
    try:
        row = get_db().execute("SELECT COUNT(*) AS cnt FROM leads").fetchone()
        lead_count = row["cnt"]
    except Exception:
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "app": settings.app_name,
        "env": settings.app_env,
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": db_status,
            "lead_count": lead_count,
        },
    }