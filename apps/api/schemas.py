from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


VALID_LEAD_STATUSES = {"new", "contacted", "closed", "not_interested"}


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
    status: str = "new"
    created_at: str


class LeadStatusUpdate(BaseModel):
    status: str = Field(min_length=1)


class WebIntakePayload(BaseModel):
    nombre: str = Field(min_length=1)
    email: EmailStr
    telefono: str | None = None
    interes: str | None = None
    mensaje: str | None = None
    origen: str | None = None


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
    status: str = "new"
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
    status: str = "new"
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


ALLOWED_LOSS_REASONS = Literal[
    "price", "timing", "competitor", "no_need", "no_response", "other"
]

ALLOWED_CHANNELS = Literal["email", "phone", "whatsapp", "other"]
ALLOWED_DIRECTIONS = Literal["outbound"]
ALLOWED_ATTEMPT_TYPES = Literal["first_contact", "follow_up", "re_engage"]
ALLOWED_ATTEMPT_STATUSES = Literal["sent", "answered", "no_answer", "failed", "bounced"]
ALLOWED_PROVIDERS = Literal["manual", "n8n", "api", "other"]


class OutcomeRequest(BaseModel):
    lead_id: int
    outcome: ALLOWED_OUTCOMES
    reason: str | None = None
    notes: str | None = None
    loss_reason: ALLOWED_LOSS_REASONS | None = None
    recorded_by: str = "system"


class OutcomeResponse(BaseModel):
    lead_id: int
    outcome: str
    reason: str | None
    notes: str | None
    loss_reason: str | None = None
    recorded_by: str = "system"
    recorded_at: str


class OutcomeHistoryEntry(BaseModel):
    outcome: str
    loss_reason: str | None
    reason: str | None
    notes: str | None
    recorded_by: str
    recorded_at: str


class OutcomeHistoryResponse(BaseModel):
    lead_id: int
    current: OutcomeHistoryEntry | None
    history: list[OutcomeHistoryEntry]
    total_changes: int


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
    last_contacted_at: str | None = None
    contact_attempts_count: int = 0
    recently_contacted: bool = False


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
    last_contacted_at: str | None = None
    contact_attempts_count: int = 0
    recently_contacted: bool = False


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
    last_contacted_at: str | None = None
    contact_attempts_count: int = 0
    recently_contacted: bool = False


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
    last_contacted_at: str | None = None
    contact_attempts_count: int = 0
    recently_contacted: bool = False


class FollowupQueueResponse(BaseModel):
    generated_at: str
    total: int
    items: list[FollowupItem]


# --- Commercial Intelligence Phase B ---


class LossReasonCounts(BaseModel):
    price: int = 0
    timing: int = 0
    competitor: int = 0
    no_need: int = 0
    no_response: int = 0
    other: int = 0
    unspecified: int = 0


class LossAnalysisBySource(BaseModel):
    source: str
    total_lost: int
    top_reason: str | None
    reasons: LossReasonCounts


class LossAnalysisResponse(BaseModel):
    generated_at: str
    source_filter: str | None
    total_lost: int
    by_reason: LossReasonCounts
    top_reason: str | None
    by_source: list[LossAnalysisBySource]


class ScoreEffectivenessBucket(BaseModel):
    range: str
    total: int
    contacted_or_beyond: int
    qualified_or_beyond: int
    won: int
    lost: int
    bad_fit: int
    no_answer: int
    contact_rate: float
    qualification_rate: float
    win_rate_on_terminal: float


class ScoreEffectivenessResponse(BaseModel):
    generated_at: str
    source_filter: str | None
    total_with_outcomes: int
    buckets: list[ScoreEffectivenessBucket]
    scoring_accuracy_signal: str


class CohortItem(BaseModel):
    month: str
    leads_created: int
    with_outcomes: int
    contacted_or_beyond: int
    qualified_or_beyond: int
    won: int
    lost: int
    bad_fit: int
    no_answer: int
    avg_score: float
    contact_rate: float
    qualification_rate: float
    win_rate_on_terminal: float


class CohortsResponse(BaseModel):
    generated_at: str
    source_filter: str | None
    months_requested: int
    cohorts: list[CohortItem]


# --- Contact Attempts ---


class ContactAttemptRequest(BaseModel):
    lead_id: int
    channel: ALLOWED_CHANNELS
    direction: ALLOWED_DIRECTIONS = "outbound"
    attempt_type: ALLOWED_ATTEMPT_TYPES
    status: ALLOWED_ATTEMPT_STATUSES
    provider: ALLOWED_PROVIDERS = "manual"
    note: str | None = None
    external_ref: str | None = None


class ContactAttemptResponse(BaseModel):
    id: int
    lead_id: int
    channel: str
    direction: str
    attempt_type: str
    status: str
    provider: str
    note: str | None
    external_ref: str | None
    created_at: str


class ContactAttemptSummaryResponse(BaseModel):
    lead_id: int
    attempt_count: int
    last_contacted_at: str | None
    last_attempt_status: str | None
    last_channel: str | None
    recent_attempts: list[ContactAttemptResponse]
