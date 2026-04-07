from typing import Literal

from pydantic import BaseModel, Field


# --- Case ---

class CaseCreate(BaseModel):
    title: str = Field(min_length=1)
    case_type: str = Field(min_length=1)
    summary: str | None = None


class CaseResponse(BaseModel):
    id: int
    title: str
    case_type: str
    status: str
    summary: str | None
    created_at: str
    updated_at: str


# --- PersonEntity ---

class PersonEntityCreate(BaseModel):
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    entity_type: Literal["person", "organization", "unknown"] = "person"
    notes: str | None = None


class PersonEntityResponse(BaseModel):
    id: int
    case_id: int
    name: str
    role: str
    entity_type: str
    notes: str | None
    created_at: str


# --- TimelineEvent ---

class TimelineEventCreate(BaseModel):
    event_date: str = Field(min_length=1)
    event_end_date: str | None = None
    description: str = Field(min_length=1)
    source_description: str | None = None
    confidence: Literal["high", "medium", "low", "unknown"] = "unknown"


class TimelineEventResponse(BaseModel):
    id: int
    case_id: int
    event_date: str
    event_end_date: str | None
    description: str
    source_description: str | None
    confidence: str
    created_at: str


class TimelineEventUpdate(BaseModel):
    event_date: str | None = None
    event_end_date: str | None = None
    description: str | None = None
    source_description: str | None = None
    confidence: Literal["high", "medium", "low", "unknown"] | None = None


# --- EvidenceItem ---

class EvidenceItemCreate(BaseModel):
    title: str = Field(min_length=1)
    evidence_type: str = Field(min_length=1)
    location: str | None = None
    description: str | None = None


class EvidenceItemResponse(BaseModel):
    id: int
    case_id: int
    title: str
    evidence_type: str
    location: str | None
    description: str | None
    created_at: str


# --- LegalIssue ---

class LegalIssueCreate(BaseModel):
    title: str = Field(min_length=1)
    issue_type: str = Field(min_length=1)
    analysis: str | None = None


class LegalIssueResponse(BaseModel):
    id: int
    case_id: int
    title: str
    issue_type: str
    status: str
    analysis: str | None
    created_at: str
    updated_at: str


class LegalIssueUpdate(BaseModel):
    title: str | None = None
    issue_type: str | None = None
    status: str | None = None
    analysis: str | None = None


# --- StrategyNote ---

class StrategyNoteCreate(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)


class StrategyNoteResponse(BaseModel):
    id: int
    case_id: int
    title: str
    content: str
    created_at: str


class StrategyNoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


# --- AnalysisArtifact ---

# --- Document ---

class DocumentCreate(BaseModel):
    document_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_ref: str | None = None
    source_hash: str | None = None
    notes: str | None = None


class DocumentResponse(BaseModel):
    id: int
    case_id: int
    document_type: str
    title: str
    source_ref: str | None
    source_hash: str | None
    notes: str | None
    created_at: str
    imported_at: str


# --- EvidenceChunk ---

class EvidenceChunkCreate(BaseModel):
    document_id: int
    text: str = Field(min_length=1)
    page_from: int | None = None
    page_to: int | None = None
    location_label: str | None = None
    timestamp_ref: str | None = None


class EvidenceChunkResponse(BaseModel):
    id: int
    case_id: int
    document_id: int
    text: str
    page_from: int | None
    page_to: int | None
    location_label: str | None
    timestamp_ref: str | None
    created_at: str


# --- AnalysisArtifact ---

class AnalysisArtifactCreate(BaseModel):
    artifact_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    status: Literal["draft", "final"] = "draft"


class AnalysisArtifactUpdate(BaseModel):
    artifact_type: str | None = None
    title: str | None = None
    content: str | None = None
    status: Literal["draft", "final"] | None = None


class AnalysisArtifactResponse(BaseModel):
    id: int
    case_id: int
    artifact_type: str
    title: str
    content: str
    status: str
    created_at: str
    updated_at: str


# --- Source-anchored chunk links ---

class ChunkLinkCreate(BaseModel):
    chunk_id: int
    relation_type: str | None = None


class LinkedChunkResponse(BaseModel):
    link_id: int
    chunk_id: int
    document_id: int
    document_title: str
    text: str
    page_from: int | None
    page_to: int | None
    location_label: str | None
    timestamp_ref: str | None
    source_ref: str | None
    relation_type: str | None
    linked_at: str


# --- Case coverage / source-grounding summary ---

class UnlinkedItem(BaseModel):
    id: int
    label: str


class EntityCoverageSection(BaseModel):
    total: int
    linked: int
    unlinked: int
    unlinked_items: list[UnlinkedItem]


# --- Case audit ---

class AuditEventResponse(BaseModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: int
    origin_module: str
    payload: str
    created_at: str


class CaseAuditResponse(BaseModel):
    case_id: int
    total_events: int
    events: list[AuditEventResponse]


# --- Case coverage ---

class CaseCoverageResponse(BaseModel):
    case_id: int
    title: str
    documents_count: int
    evidence_chunks_count: int
    timeline_events: EntityCoverageSection
    legal_issues: EntityCoverageSection
    strategy_notes: EntityCoverageSection
    analysis_artifacts: EntityCoverageSection
