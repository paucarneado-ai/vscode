import csv
import io
from datetime import datetime, timezone
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from apps.api.auth import require_api_key
from apps.api.ratelimit import require_rate_limit
from apps.api.schemas import (
    LeadCreate,
    LeadCreateResult,
    LeadDeliveryResponse,
    LeadOperationalSummary,
    LeadPackResponse,
    LeadResponse,
    LeadStatusUpdate,
    WebhookLeadPayload,
    WebIntakePayload,
    WorklistGroup,
    WorklistResponse,
)
from apps.api.services.actions import ACTION_PRIORITY
from apps.api.services.intake import (
    create_lead as _create_lead_internal,
    get_lead_by_id,
    get_leads_summary_data,
    InvalidStatusError,
    normalize_web_intake,
    normalize_webhook_payload,
    query_leads,
    query_leads_for_export,
    update_lead_status,
    ProviderValidationError,
    SourceValidationError,
)
from apps.api.services.leadpack import render_lead_pack_html, render_lead_pack_text
from apps.api.services.operational import (
    get_actionable_leads as _get_actionable_leads,
    get_lead_pack_by_id,
    get_lead_operational_by_id,
)


router = APIRouter(dependencies=[Depends(require_api_key)])
public_router = APIRouter(dependencies=[Depends(require_rate_limit)])  # Public, rate-limited


@router.post("/leads", response_model=LeadCreateResult)
def create_lead(payload: LeadCreate) -> LeadCreateResult:
    try:
        result, status = _create_lead_internal(payload)
    except SourceValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if status == 409:
        return JSONResponse(status_code=409, content=result.model_dump())
    return result


@router.post("/leads/ingest")
def ingest_leads(items: list[LeadCreate]) -> dict:
    created = 0
    duplicates = 0
    errors: list[dict] = []

    for i, item in enumerate(items):
        try:
            _, status = _create_lead_internal(item)
            if status == 200:
                created += 1
            elif status == 409:
                duplicates += 1
        except Exception as exc:
            errors.append({"index": i, "email": item.email, "error": str(exc)})

    return {
        "total": len(items),
        "created": created,
        "duplicates": duplicates,
        "errors": errors,
    }


@public_router.post("/leads/intake/web")
def web_intake(payload: WebIntakePayload) -> dict:
    lead_create = normalize_web_intake(payload)
    result, status = _create_lead_internal(lead_create)
    if status == 409:
        return JSONResponse(
            status_code=409,
            content={"status": "duplicate", "lead_id": result.lead.id},
        )
    return {"status": "accepted", "lead_id": result.lead.id}


@router.post("/leads/webhook/{provider}")
def webhook_ingest(provider: str, payload: WebhookLeadPayload) -> dict:
    try:
        lead_create = normalize_webhook_payload(provider, payload)
    except ProviderValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    result, status = _create_lead_internal(lead_create)
    if status == 409:
        return JSONResponse(
            status_code=409,
            content={"status": "duplicate", "lead_id": result.lead.id},
        )
    return {"status": "accepted", "lead_id": result.lead.id}


@router.post("/leads/webhook/{provider}/batch")
def webhook_ingest_batch(provider: str, items: list[WebhookLeadPayload]) -> dict:
    try:
        # Validate provider once, not per item
        test_payload = WebhookLeadPayload(name="test", email="test@test.com")
        normalize_webhook_payload(provider, test_payload)
    except ProviderValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    created = 0
    duplicates = 0
    errors: list[dict] = []

    for i, item in enumerate(items):
        try:
            lead_create = normalize_webhook_payload(provider, item)
            _, status = _create_lead_internal(lead_create)
            if status == 200:
                created += 1
            elif status == 409:
                duplicates += 1
        except Exception as exc:
            errors.append({"index": i, "email": item.email, "error": str(exc)})

    return {
        "total": len(items),
        "created": created,
        "duplicates": duplicates,
        "errors": errors,
    }


@router.get("/leads", response_model=list[LeadResponse])
def list_leads(
    source: str | None = None,
    min_score: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1),
    offset: int | None = Query(default=None, ge=0),
    q: str | None = None,
    status: str | None = None,
) -> list[LeadResponse]:
    try:
        return query_leads(source, min_score, limit, offset, q, status)
    except InvalidStatusError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/leads/summary")
def get_leads_summary(
    source: str | None = None,
    min_score: int | None = Query(default=None, ge=0),
    q: str | None = None,
) -> dict:
    return get_leads_summary_data(source, min_score, q)


@router.get("/leads/actionable", response_model=list[LeadOperationalSummary])
def get_actionable_leads(
    source: str | None = None,
    limit: int | None = Query(default=None, ge=1),
) -> list[LeadOperationalSummary]:
    return _get_actionable_leads(source, limit)


@router.get("/leads/actionable/worklist", response_model=WorklistResponse)
def get_actionable_worklist(
    source: str | None = None,
    limit: int | None = Query(default=None, ge=1),
) -> WorklistResponse:
    leads = _get_actionable_leads(source, limit)
    grouped: dict[str, list[LeadOperationalSummary]] = defaultdict(list)
    for lead in leads:
        grouped[lead.next_action].append(lead)
    priority_set = set(ACTION_PRIORITY)
    ordered_actions = [a for a in ACTION_PRIORITY if a in grouped]
    ordered_actions += [a for a in grouped if a not in priority_set]
    groups = [
        WorklistGroup(next_action=action, count=len(grouped[action]), leads=grouped[action])
        for action in ordered_actions
    ]
    return WorklistResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=len(leads),
        groups=groups,
    )


CSV_COLUMNS = ["id", "name", "email", "source", "score", "notes"]


@router.get("/leads/export.csv", response_class=PlainTextResponse)
def export_leads_csv(
    source: str | None = None,
    min_score: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1),
    offset: int | None = Query(default=None, ge=0),
    q: str | None = None,
) -> PlainTextResponse:
    rows = query_leads_for_export(source, min_score, limit, offset, q)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for d in rows:
        writer.writerow([d[col] for col in CSV_COLUMNS])

    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@router.get("/leads/{lead_id}", response_model=LeadResponse)
def get_lead(lead_id: int) -> LeadResponse:
    lead = get_lead_by_id(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.patch("/leads/{lead_id}/status", response_model=LeadResponse)
def patch_lead_status(lead_id: int, body: LeadStatusUpdate) -> LeadResponse:
    try:
        lead = update_lead_status(lead_id, body.status)
    except InvalidStatusError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.get("/leads/{lead_id}/pack", response_model=LeadPackResponse)
def get_lead_pack(lead_id: int) -> LeadPackResponse:
    pack = get_lead_pack_by_id(lead_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return pack


@router.get("/leads/{lead_id}/pack/html", response_class=HTMLResponse)
def get_lead_pack_html(lead_id: int) -> HTMLResponse:
    pack = get_lead_pack(lead_id)
    return HTMLResponse(content=render_lead_pack_html(pack))


@router.get("/leads/{lead_id}/pack.txt", response_class=PlainTextResponse)
def get_lead_pack_text(lead_id: int) -> PlainTextResponse:
    pack = get_lead_pack(lead_id)
    return PlainTextResponse(content=render_lead_pack_text(pack))


@router.get("/leads/{lead_id}/operational", response_model=LeadOperationalSummary)
def get_lead_operational(lead_id: int) -> LeadOperationalSummary:
    result = get_lead_operational_by_id(lead_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return result


@router.get("/leads/{lead_id}/delivery", response_model=LeadDeliveryResponse)
def get_lead_delivery(lead_id: int) -> LeadDeliveryResponse:
    pack = get_lead_pack(lead_id)
    generated_at = datetime.now(timezone.utc).isoformat()
    if pack.alert:
        message = f"ALERT: lead requires attention — {pack.next_action}"
    else:
        message = f"Lead pack generated — next: {pack.next_action}"
    return LeadDeliveryResponse(
        lead_id=pack.lead_id,
        delivery_status="generated",
        channel="api",
        generated_at=generated_at,
        next_action=pack.next_action,
        alert=pack.alert,
        pack=pack,
        message=message,
    )
