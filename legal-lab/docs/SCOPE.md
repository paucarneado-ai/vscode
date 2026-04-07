# legal-lab — Scope

Isolated legal-intelligence foundation. No shared imports with `apps/api/` or `trading-lab/`.

## Reused patterns (copied and adapted)

1. **Config** — frozen dataclass + env vars. Copied from `apps/api/config.py`. Renamed env vars to `LEGAL_LAB_*`. Removed rate limit fields.
2. **Auth** — API key header with dev/test bypass, fail-closed in production. Copied from `apps/api/auth.py`. Renamed to `LEGAL_LAB_API_KEY`.
3. **DB singleton** — `get_db()` / `reset_db()` pattern copied from `apps/api/db.py`. All DDL written fresh for legal domain.
4. **Health routes** — `/health` and `/health/detail` pattern copied from `apps/api/routes/health.py`. Table names updated.
5. **Test isolation** — temp SQLite DB per test module, `object.__setattr__()` for config override. Pattern derived from multiple existing test files.

## Adapted (not copied as-is)

1. **Event spine** — function signature from `apps/api/events.py`. Silent-failure (`except Exception: pass`) replaced with logged failure + boolean return. Internal `db.commit()` removed — caller controls transaction.

## Intentionally not reused

- Lead schemas, scoring, actions, leadpack, intake, operational composition
- Rate limiter (no public endpoints)
- Internal operations routes (2200 lines of lead lifecycle)
- Intelligence/analytics routes
- Admin/boat catalog
- Demo route
- Pathway Discovery module
- Trading Lab domain logic
- Static site / deploy scripts
- Shared core extraction (core/ remains empty)

## Domain entities

**Foundation (block 1):** Case, PersonEntity, TimelineEvent, EvidenceItem, LegalIssue, StrategyNote, AnalysisArtifact.

**Source-grounding (block 2):** Document, EvidenceChunk.

### Source-grounding layer

Documents and evidence chunks form the source-grounding layer for criminal defense work. Every later analytical feature (chronology synthesis, contradiction detection, source-anchored memos) depends on being able to trace claims back to a specific document, page range, and text excerpt.

**Document** — a registered source document belonging to a case. Carries `document_type`, `title`, `source_ref` (path or URI), optional `source_hash`, and `notes`. Does not store file content — only metadata.

**EvidenceChunk** — a specific excerpt from a document. Carries `text` (the excerpt), optional `page_from`/`page_to` (page range), `location_label` (e.g. "paragraph 2", "exhibit header"), and `timestamp_ref` (date/time referenced in the text). Belongs to exactly one document and one case. The chunk's `case_id` must match the document's `case_id` — this is enforced at both route level and FK level.

**Case isolation guarantees:**
- Documents are scoped to a single case. Retrieval by document ID is always case-qualified.
- Chunks are scoped to a single case and document. Cross-case retrieval returns 404.
- Chunk creation rejects mismatches between the URL case_id and the document's case_id.
- These guarantees are tested explicitly.

**What this enables (not yet built):**
- Chronology synthesis from timestamped chunks
- Prosecution-claim vs defense-hypothesis separation anchored to source text
- Contradiction flags between chunks from different documents
- Source-anchored analysis artifacts that cite specific page ranges

**What this does NOT provide:**
- File upload or content ingestion — documents are metadata references only
- OCR or text extraction — chunks are pre-extracted text registered via API
- Embeddings or vector search — retrieval is by case/document scope, not semantic

## Transactional guarantee

All route handlers use a single SQLite connection singleton (`get_db()`). The primary INSERT and the audit event INSERT share the same connection and therefore the same implicit transaction. `db.commit()` persists both atomically; `db.rollback()` discards both.

If `emit_event()` fails, the route rolls back the entire transaction and returns HTTP 500. No primary write is persisted without its audit event.

**This guarantee holds because:**
- `get_db()` returns a process-global singleton connection.
- The application runs as a single-worker process.
- SQLite serializes all writes on one connection.

**This guarantee would break if:**
- The application moves to connection pooling (each call to `get_db()` could return a different connection).
- Multiple worker processes are used (each would have its own singleton).
- The database engine changes to PostgreSQL or similar (connection semantics differ).

At that point, the transactional coupling between primary writes and event writes must be re-evaluated — likely by introducing explicit transaction context management.

## Source-anchored cross-reference layer (block 3)

Analytical entities can now be explicitly linked to evidence chunks. This makes it structurally possible to say "this timeline event is supported by chunk X from document Y, page 5."

**Linkable entities:** TimelineEvent, LegalIssue, StrategyNote, AnalysisArtifact.

**Link tables:** 4 explicit tables, one per parent entity type. Each has:
- composite FK to parent entity `(entity_id, case_id)` — prevents cross-case parent reference
- composite FK to evidence chunk `(chunk_id, case_id)` — prevents cross-case chunk reference
- `UNIQUE (entity_id, chunk_id)` — prevents duplicate links
- optional `relation_type` (e.g. "supports", "contradicts", "cites")

**Retrieval:** Each parent entity has a `/links` GET endpoint that returns linked chunks with joined document metadata (title, source_ref). This is the minimal read surface needed for source-anchored review.

**Integrity:** Case isolation is enforced at both API level (route checks) and DB level (composite FKs). The schema verification detects missing composite FKs on startup and fails loudly for pre-existing databases.

**What this enables (not yet built):**
- Source-anchored memos that list their evidence basis
- Contradiction detection between chunks linked to the same issue
- Chronology synthesis that cites specific document pages
- Defense workbench views showing which claims have source support and which do not

## Case coverage surface (block 4)

`GET /cases/{case_id}/coverage` returns a read-only summary of source-grounding status for a case.

**What it reports:**
- Case metadata (id, title)
- Total documents and evidence chunks registered
- For each linkable entity type (timeline events, legal issues, strategy notes, analysis artifacts): total count, how many are source-linked, how many are unlinked, and a compact list of unlinked items (id + label)

**Why it matters:** A defense team needs to see at a glance which analytical claims have evidence support and which are still ungrounded. This is the first step toward "which parts of our analysis lack source backing."

**What it does NOT do:**
- No reasoning about whether links are strong or weak
- No automatic gap detection or recommendation
- No chronology, contradiction, or claim analysis
- No write operations — purely read-only

## Case audit surface (block 5)

`GET /cases/{case_id}/audit` returns the chronologically ordered audit event history for one case.

**What it reports:** All events where either `entity_type='case' AND entity_id=case_id` (case creation) or `json_extract(payload, '$.case_id') = case_id` (child entity, document, chunk, and link events). Returns event id, type, entity_type, entity_id, origin_module, raw payload, and created_at.

**Event coverage:** case.created, entity.created, timeline.created, evidence.created, issue.created, note.created, artifact.created, document.created, chunk.created, link.*.created.

**Case-scoping limitation:** The events table has no native `case_id` column. Case-scoping relies on two conventions: (1) case creation events have `entity_type='case'` with `entity_id` equal to the case ID, (2) all other events include `"case_id": N` in the JSON payload. Events that violate this convention (if any were added without case_id in the payload) would not appear. This is a known trade-off — adding a case_id column to the events table would be a schema change requiring a separate hardening block.

**What it does NOT do:**
- No filtering by event type, date range, or entity type
- No pagination
- No write operations
- No event deletion or modification
- No aggregation or analytics over events

## Entity update surface (block 6)

Four PATCH endpoints allow partial updates to analytical entities:

- `PATCH /cases/{case_id}/timeline/{event_id}` — event_date, event_end_date, description, source_description, confidence
- `PATCH /cases/{case_id}/issues/{issue_id}` — title, issue_type, status, analysis
- `PATCH /cases/{case_id}/notes/{note_id}` — title, content
- `PATCH /cases/{case_id}/artifacts/{artifact_id}` — artifact_type, title, content, status

**Partial update semantics:** Only fields present in the request body are modified. Omitted fields remain unchanged. `updated_at` is set automatically where the table has that column (legal_issues, analysis_artifacts).

**Audit:** Every successful update emits an audit event (e.g. `timeline_event.updated`) with the list of updated field names in the payload. Event failure triggers rollback — consistent with all other write paths.

**Why this block exists:** A defense workbench needs to correct, refine, and mature analysis objects after creation. Without update capability, every correction requires deleting and recreating entities, losing link associations.

**Intentionally immutable (not yet updateable):** Case, PersonEntity, EvidenceItem, Document, EvidenceChunk, source-link tables. These may gain update support in future blocks if operationally needed.

## Out of scope

- RAG, OCR, document ingestion
- LLM/AI integration
- Contradiction detection engine
- Evidence-linked reasoning
- Uncertainty scoring beyond the confidence field on TimelineEvent
- Analysis artifact template generation
- Case import/export
- User management / multi-tenant auth
- Update/delete endpoints
- Pagination, filtering, search, export
- Front-end
- Deployment changes
- Migration system (idempotent DDL only)
