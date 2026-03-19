from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class LeadCreate(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    source: str = Field(min_length=1)
    notes: str | None = None


class LeadResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    source: str
    notes: str | None = None
    score: int
    created_at: str


class LeadsSummaryResponse(BaseModel):
    total_leads: int
    average_score: float
    low_score_count: int
    medium_score_count: int
    high_score_count: int
    counts_by_source: dict[str, int]


class LeadCreateResult(BaseModel):
    message: str
    lead: LeadResponse
    meta: dict[str, str]


class LeadPackResponse(BaseModel):
    lead_id: int
    created_at: str
    name: str
    email: EmailStr
    source: str
    notes: str | None = None
    score: int
    rating: str
    summary: str
    next_action: str
    alert: bool


class WebhookLeadPayload(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    notes: str | None = None


class LeadOperationalSummary(BaseModel):
    lead_id: int
    name: str
    source: str
    score: int
    rating: str
    next_action: str
    instruction: str
    alert: bool
    summary: str
    created_at: str
    generated_at: str


class WorklistGroup(BaseModel):
    next_action: str
    count: int
    leads: list[LeadOperationalSummary]


class WorklistResponse(BaseModel):
    generated_at: str
    total: int
    groups: list[WorklistGroup]


class QueueResponse(BaseModel):
    generated_at: str
    total: int
    urgent_count: int
    items: list[LeadOperationalSummary]


class LeadDeliveryResponse(BaseModel):
    lead_id: int
    delivery_status: str
    channel: str
    generated_at: str
    next_action: str
    alert: bool
    pack: LeadPackResponse
    message: str


class ExternalLeadPayload(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    source: str = Field(min_length=1)
    phone: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] | None = None


class ExternalLeadResult(BaseModel):
    status: str
    lead_id: int
    score: int
    message: str


class AutomationDispatch(BaseModel):
    lead_id: int
    action: str
    instruction: str
    priority: int
    alert: bool
    payload: LeadPackResponse
    generated_at: str


class AutomationBatchResponse(BaseModel):
    generated_at: str
    total: int
    items: list[AutomationDispatch]


class ClaimRequest(BaseModel):
    lead_ids: list[int] = Field(min_length=1)


class ClaimResponse(BaseModel):
    claimed: list[int]
    already_claimed: list[int]
    not_found: list[int]


class HandoffItem(BaseModel):
    lead_id: int
    action: str
    channel: str
    instruction: str
    payload: LeadPackResponse


class HandoffBatchResponse(BaseModel):
    generated_at: str
    total: int
    items: list[HandoffItem]


class ReviewItem(BaseModel):
    lead_id: int
    name: str
    email: str
    source: str
    score: int
    rating: str
    next_action: str
    instruction: str
    alert: bool
    created_at: str


class ReviewQueueResponse(BaseModel):
    generated_at: str
    total: int
    urgent_count: int
    items: list[ReviewItem]


class ReviewClaimResponse(BaseModel):
    lead_id: int
    status: str


class OpsSnapshotResponse(BaseModel):
    generated_at: str
    total_leads: int
    actionable: int
    claimed: int
    pending_dispatch: int
    pending_review: int
    urgent: int


class ClientReadyItem(BaseModel):
    lead_id: int
    name: str
    email: str
    source: str
    score: int
    rating: str
    next_action: str
    instruction: str
    created_at: str


class ClientReadyResponse(BaseModel):
    generated_at: str
    total: int
    items: list[ClientReadyItem]


class WorklistClaimedItem(BaseModel):
    lead_id: int
    name: str
    source: str
    score: int
    claimed_at: str


class OperatorWorklistResponse(BaseModel):
    generated_at: str
    pending_review: list[ReviewItem]
    client_ready: list[ClientReadyItem]
    recently_claimed: list[WorklistClaimedItem]


class ClaimReleaseResponse(BaseModel):
    lead_id: int
    status: str


class SourceStats(BaseModel):
    source: str
    total: int
    avg_score: float
    client_ready: int
    review: int


class SourcePerformanceResponse(BaseModel):
    generated_at: str
    total_sources: int
    items: list[SourceStats]


class SourceActionItem(BaseModel):
    source: str
    total: int
    actionable: int
    avg_score: float
    client_ready: int
    review: int
    recommendation: str
    rationale: str


class SourceActionResponse(BaseModel):
    generated_at: str
    total_sources: int
    items: list[SourceActionItem]


class EventItem(BaseModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: int
    origin_module: str
    payload: dict
    created_at: str


class EventListResponse(BaseModel):
    generated_at: str
    total: int
    items: list[EventItem]


class SentinelFinding(BaseModel):
    check: str
    surface: str
    severity: str
    message: str
    recommended_action: str


class SentinelResponse(BaseModel):
    generated_at: str
    status: str
    total_findings: int
    findings: list[SentinelFinding]


class AuditFinding(BaseModel):
    check: str
    surface: str
    severity: str
    message: str
    detail: dict


class AuditResponse(BaseModel):
    generated_at: str
    status: str
    total_findings: int
    findings: list[AuditFinding]


class RedundancyFinding(BaseModel):
    type: str
    targets: list[str]
    severity: str
    message: str
    recommended_action: str
    confidence: str
    removal_risk: str
    why_now: str


class RedundancyResponse(BaseModel):
    generated_at: str
    areas_scanned: list[str]
    overall_status: str
    total_findings: int
    findings: list[RedundancyFinding]


class ScopeCriticRequest(BaseModel):
    classification: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    scope: list[str] = Field(min_length=1)
    out_of_scope: list[str] = Field(min_length=1)
    expected_files: list[str] = Field(min_length=1)
    main_risk: str = Field(min_length=1)
    minimum_acceptable: str = Field(min_length=1)


class ScopeCriticFinding(BaseModel):
    check: str
    severity: str
    message: str
    evidence: list[str]


class ScopeCriticResponse(BaseModel):
    generated_at: str
    status: str
    total_findings: int
    findings: list[ScopeCriticFinding]


class ProofVerifierRequest(BaseModel):
    block_name: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    claimed_changes: list[str] = Field(min_length=1)
    claimed_verified: list[str] = Field(min_length=1)
    claimed_not_verified: list[str]
    files_touched: list[str] = Field(min_length=1)
    tests_run: list[str]
    status_claim: str = Field(min_length=1)


class ProofVerifierFinding(BaseModel):
    check: str
    severity: str
    message: str
    evidence: list[str]
    blocks_closure: bool
    confidence: str


class ProofVerifierResponse(BaseModel):
    generated_at: str
    status: str
    total_findings: int
    findings: list[ProofVerifierFinding]


class DriftDetectorRequest(BaseModel):
    plan_expected_files: list[str] = Field(min_length=1)
    plan_out_of_scope: list[str] = Field(min_length=1)
    plan_classification: str = Field(min_length=1)
    report_files_touched: list[str] = Field(min_length=1)
    report_claimed_changes: list[str] = Field(min_length=1)
    report_classification: str = Field(min_length=1)


class DriftFinding(BaseModel):
    check: str
    severity: str
    message: str
    plan_value: list[str]
    report_value: list[str]
    requires_justification: bool


class DriftDetectorResponse(BaseModel):
    generated_at: str
    status: str
    total_findings: int
    findings: list[DriftFinding]


ALLOWED_OUTCOMES = Literal[
    "contacted", "qualified", "won", "lost", "no_answer", "bad_fit"
]


class OutcomeRequest(BaseModel):
    lead_id: int
    outcome: ALLOWED_OUTCOMES
    reason: str | None = None
    notes: str | None = None


class OutcomeResponse(BaseModel):
    lead_id: int
    outcome: str
    reason: str | None
    notes: str | None
    recorded_at: str


class OutcomeSummaryResponse(BaseModel):
    generated_at: str
    total: int
    by_outcome: dict[str, int]


class OutcomeBySourceItem(BaseModel):
    source: str
    total: int
    contacted: int
    qualified: int
    won: int
    lost: int
    no_answer: int
    bad_fit: int


class OutcomeBySourceResponse(BaseModel):
    generated_at: str
    total_sources: int
    items: list[OutcomeBySourceItem]


class SourceOutcomeActionItem(BaseModel):
    source: str
    total_outcomes: int
    contacted: int
    qualified: int
    won: int
    lost: int
    no_answer: int
    bad_fit: int
    recommendation: str
    rationale: str
    data_sufficient: bool


class SourceOutcomeActionResponse(BaseModel):
    generated_at: str
    total_sources: int
    items: list[SourceOutcomeActionItem]


class SourceIntelligenceOutcomes(BaseModel):
    contacted: int = 0
    qualified: int = 0
    won: int = 0
    lost: int = 0
    no_answer: int = 0
    bad_fit: int = 0


class SourceIntelligenceTotals(BaseModel):
    leads: int
    avg_score: float
    pending_review: int
    client_ready: int
    followup_candidates: int
    outcomes: SourceIntelligenceOutcomes


class SourceIntelligenceItem(BaseModel):
    source: str
    leads: int
    avg_score: float
    pending_review: int
    client_ready: int
    followup_candidates: int
    outcomes: SourceIntelligenceOutcomes
    recommendation: str
    rationale: str
    data_sufficient: bool


class SourceIntelligenceResponse(BaseModel):
    generated_at: str
    total_sources: int
    totals: SourceIntelligenceTotals
    by_source: list[SourceIntelligenceItem]


class DailyActionSummary(BaseModel):
    pending_review: int
    client_ready: int
    followup_candidates: int
    source_warnings: int


class DailyReviewItem(BaseModel):
    lead_id: int
    name: str
    source: str
    score: int
    rating: str
    next_action: str
    alert: bool


class DailyClientReadyItem(BaseModel):
    lead_id: int
    name: str
    source: str
    score: int
    rating: str
    next_action: str


class DailyFollowupItem(BaseModel):
    lead_id: int
    name: str
    source: str
    score: int
    outcome_recorded_at: str


class DailySourceWarning(BaseModel):
    source: str
    recommendation: str
    rationale: str
    total_outcomes: int


class DailyActionsResponse(BaseModel):
    generated_at: str
    summary: DailyActionSummary
    top_review: list[DailyReviewItem]
    top_client_ready: list[DailyClientReadyItem]
    top_followup: list[DailyFollowupItem]
    source_warnings: list[DailySourceWarning]


class FollowupAutomationPayload(BaseModel):
    name: str
    email: str
    source: str
    score: int
    rating: str
    instruction: str
    suggested_message: str


class FollowupAutomationItem(BaseModel):
    lead_id: int
    channel: str
    action: str
    priority: int
    payload: FollowupAutomationPayload


class FollowupAutomationResponse(BaseModel):
    generated_at: str
    total: int
    items: list[FollowupAutomationItem]


class FollowupHandoffItem(BaseModel):
    lead_id: int
    name: str
    email: str
    source: str
    score: int
    rating: str
    outcome_recorded_at: str
    channel: str
    action: str
    instruction: str
    suggested_message: str


class FollowupHandoffResponse(BaseModel):
    generated_at: str
    total: int
    items: list[FollowupHandoffItem]


class FollowupItem(BaseModel):
    lead_id: int
    name: str
    email: str
    source: str
    score: int
    rating: str
    next_action: str
    instruction: str
    outcome: str
    outcome_reason: str | None
    outcome_notes: str | None
    outcome_recorded_at: str


class FollowupQueueResponse(BaseModel):
    generated_at: str
    total: int
    items: list[FollowupItem]

# --- TEMPORARY: rescue/openclaw-import-phase1 ---
# These definitions are required by apps/api/services/intake.py (imported in phase 1).
# They must be properly merged into this file during phase 2.
# Do not add more definitions here — resolve in phase 2 merge instead.

VALID_LEAD_STATUSES = {"new", "contacted", "closed", "not_interested"}


class LeadStatusUpdate(BaseModel):
    status: str = Field(min_length=1)


class WebIntakePayload(BaseModel):
    nombre: str = Field(min_length=1)
    email: EmailStr
    telefono: str | None = None
    interes: str | None = None
    mensaje: str | None = None
    origen: str | None = None
