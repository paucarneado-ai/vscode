"""Data models for pathway_discovery. All internal — no Pydantic, no API."""

from dataclasses import dataclass, field
from enum import Enum


@dataclass
class ModuleRegistryEntry:
    module_id: str
    file_path: str
    module_kind: str  # route | service | schema | util | infra | other
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    imports_from: list[str] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)
    line_count: int = 0
    fan_out: int = 0
    fan_in: int = 0
    protected: bool = False


@dataclass
class FunctionRegistryEntry:
    module_id: str
    function_name: str
    line_number: int
    arg_names: list[str] = field(default_factory=list)
    calls_made: list[str] = field(default_factory=list)
    line_count: int = 0


@dataclass
class PathwayRegistryEntry:
    pathway_id: str
    source_module: str
    target_module: str
    via_import: str
    hop_count: int = 1


@dataclass
class InteractionTrace:
    caller_module: str
    caller_function: str
    callee_module: str | None
    callee_function: str
    line_number: int
    file_path: str
    args_passed: list[str] = field(default_factory=list)
    resolution_kind: str = "direct"
    confidence: float = 1.0
    confidence_reason: str = ""


class CandidateType(Enum):
    LONG_PATH = "long_path"
    REDUNDANT_TRANSFORM = "redundant_transform"
    PROHIBITED_CONNECTION = "prohibited_connection"
    SHARED_FUNCTION = "shared_function"
    GENERIC_CONTRACT = "generic_contract"
    DUPLICATE_LOGIC = "duplicate_logic"
    DIRECT_PATH = "direct_path"


@dataclass
class CandidatePathway:
    candidate_id: str
    candidate_type: CandidateType
    description: str
    modules_involved: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    current_hops: int = 0
    proposed_hops: int = 0
    call_frequency: str = "unknown"
    confidence: float = 1.0
    raw_confidence: float = 1.0
    orchestrator_penalty: float = 0.0
    confidence_reason: str = ""
    impact_scope: str = "local"
    estimated_effort: str = "small"
    risk_level: str = "low"
    touches_protected: bool = False
    estimated_token_saving: int = 0
    estimated_latency_saving_ms: float = 0.0
    occurrence_count: int = 1
    depends_on_known_debt: bool = False
    known_debt_reference: str = ""
    stable_fingerprint: str = ""
    # Intermediate role classification (long_path only)
    intermediate_role: str = "unknown"  # unknown | pass_through | shared_composer | contract_translator
    role_confidence: float = 0.0
    role_reason: str = ""


@dataclass
class PathwayRecommendation:
    recommendation_id: str
    candidate: CandidatePathway
    score: float
    score_breakdown: dict = field(default_factory=dict)
    priority: str = "low"
    review_bucket: str = "ignore"
    governance_status: str = "DEFERRED"
    action: str = "no_action"
    rationale: str = ""
    seen_in_previous_audit: bool = False
    watchlist_age: int = 0
    escalated_watchlist: bool = False
    watchlist_severity_score: float = 0.0
    watchlist_escalation_reason: str = ""
    # Known debt lifecycle
    debt_status: str = ""  # active | review_due | archived
    debt_age: int = 0
    # Review queue
    in_review_queue: bool = False
    operator_status: str = ""  # unreviewed | keep | monitor | schedule | resolved
    operator_note: str = ""
    why_now: str = ""
    intervention_hint: str = ""
    reviewed_at: str = ""
    decision_reason: str = ""
    inactive: bool = False


@dataclass
class ModuleDrift:
    module_id: str
    fan_out_old: int
    fan_out_new: int
    fan_in_old: int
    fan_in_new: int
    classification: str  # stable | mild_drift | notable_drift | critical_drift


