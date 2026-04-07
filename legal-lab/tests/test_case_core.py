"""Core case lifecycle tests: create case, add child entities, query back, FK enforcement."""

import tempfile

from fastapi.testclient import TestClient

from legal_lab import db as db_module
from legal_lab.config import settings

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
db_module.DATABASE_PATH = _tmp.name
db_module.reset_db()
db_module.init_db()

from legal_lab.app import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def _headers():
    return {"X-API-Key": "test"} if settings.api_key else {}


def _create_case(title="Test Case", case_type="test"):
    resp = client.post("/cases", json={
        "title": title, "case_type": case_type,
    }, headers=_headers())
    assert resp.status_code == 201
    return resp.json()["id"]


class TestCaseCRUD:
    def test_create_case_returns_201_with_correct_fields(self):
        resp = client.post("/cases", json={
            "title": "Smith v. Jones",
            "case_type": "civil_litigation",
            "summary": "Contract dispute over property sale",
        }, headers=_headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Smith v. Jones"
        assert data["case_type"] == "civil_litigation"
        assert data["status"] == "open"
        assert data["summary"] == "Contract dispute over property sale"
        assert isinstance(data["id"], int)
        assert "created_at" in data
        assert "updated_at" in data

    def test_list_cases_contains_created_case(self):
        case_id = _create_case("Findable Case")
        resp = client.get("/cases", headers=_headers())
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json()]
        assert case_id in ids

    def test_get_case_by_id_returns_correct_case(self):
        case_id = _create_case("State v. Doe", "criminal")
        resp = client.get(f"/cases/{case_id}", headers=_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "State v. Doe"
        assert data["case_type"] == "criminal"
        assert data["id"] == case_id

    def test_get_nonexistent_case_returns_404(self):
        resp = client.get("/cases/99999", headers=_headers())
        assert resp.status_code == 404

    def test_create_case_missing_required_field_returns_422(self):
        resp = client.post("/cases", json={
            "case_type": "civil_litigation",
        }, headers=_headers())
        assert resp.status_code == 422

    def test_create_case_empty_title_returns_422(self):
        resp = client.post("/cases", json={
            "title": "",
            "case_type": "civil_litigation",
        }, headers=_headers())
        assert resp.status_code == 422


class TestPersonEntity:
    def setup_method(self):
        self.case_id = _create_case("Entity Test")

    def test_create_entity(self):
        resp = client.post(f"/cases/{self.case_id}/entities", json={
            "name": "John Smith",
            "role": "plaintiff",
            "entity_type": "person",
            "notes": "Primary claimant",
        }, headers=_headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "John Smith"
        assert data["case_id"] == self.case_id

    def test_list_entities_scoped_to_case(self):
        other_case = _create_case("Other Case")
        client.post(f"/cases/{self.case_id}/entities", json={
            "name": "Alice", "role": "witness",
        }, headers=_headers())
        client.post(f"/cases/{other_case}/entities", json={
            "name": "Bob", "role": "defendant",
        }, headers=_headers())

        resp = client.get(f"/cases/{self.case_id}/entities", headers=_headers())
        assert resp.status_code == 200
        names = [e["name"] for e in resp.json()]
        assert "Alice" in names
        assert "Bob" not in names

    def test_entity_on_nonexistent_case(self):
        resp = client.post("/cases/99999/entities", json={
            "name": "Nobody", "role": "test",
        }, headers=_headers())
        assert resp.status_code == 404


class TestTimelineEvent:
    def setup_method(self):
        self.case_id = _create_case("Timeline Test")

    def test_create_timeline_event(self):
        resp = client.post(f"/cases/{self.case_id}/timeline", json={
            "event_date": "2024-01-15",
            "description": "Contract signed",
            "source_description": "Exhibit A - signed contract",
            "confidence": "high",
        }, headers=_headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["event_date"] == "2024-01-15"
        assert data["confidence"] == "high"

    def test_timeline_with_date_range(self):
        resp = client.post(f"/cases/{self.case_id}/timeline", json={
            "event_date": "2024-02-01",
            "event_end_date": "2024-02-15",
            "description": "Negotiation period",
        }, headers=_headers())
        assert resp.status_code == 201
        assert resp.json()["event_end_date"] == "2024-02-15"

    def test_list_timeline_ordered_by_date(self):
        client.post(f"/cases/{self.case_id}/timeline", json={
            "event_date": "2024-03-01", "description": "Later event",
        }, headers=_headers())
        client.post(f"/cases/{self.case_id}/timeline", json={
            "event_date": "2024-01-01", "description": "Earlier event",
        }, headers=_headers())

        resp = client.get(f"/cases/{self.case_id}/timeline", headers=_headers())
        events = resp.json()
        assert len(events) == 2
        dates = [e["event_date"] for e in events]
        assert dates == sorted(dates)

    def test_timeline_on_nonexistent_case(self):
        resp = client.post("/cases/99999/timeline", json={
            "event_date": "2024-01-01", "description": "test",
        }, headers=_headers())
        assert resp.status_code == 404


class TestEvidenceItem:
    def setup_method(self):
        self.case_id = _create_case("Evidence Test")

    def test_create_evidence(self):
        resp = client.post(f"/cases/{self.case_id}/evidence", json={
            "title": "Signed Contract",
            "evidence_type": "document",
            "location": "Binder 1, Tab 3",
            "description": "Original signed copy of purchase agreement",
        }, headers=_headers())
        assert resp.status_code == 201
        assert resp.json()["evidence_type"] == "document"

    def test_list_evidence(self):
        client.post(f"/cases/{self.case_id}/evidence", json={
            "title": "Photo 1", "evidence_type": "photograph",
        }, headers=_headers())
        resp = client.get(f"/cases/{self.case_id}/evidence", headers=_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_evidence_on_nonexistent_case(self):
        resp = client.post("/cases/99999/evidence", json={
            "title": "test", "evidence_type": "document",
        }, headers=_headers())
        assert resp.status_code == 404


class TestLegalIssue:
    def setup_method(self):
        self.case_id = _create_case("Issues Test")

    def test_create_issue(self):
        resp = client.post(f"/cases/{self.case_id}/issues", json={
            "title": "Statute of limitations",
            "issue_type": "procedural",
            "analysis": "Need to verify filing date against 3-year SOL",
        }, headers=_headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "open"
        assert data["issue_type"] == "procedural"

    def test_list_issues(self):
        client.post(f"/cases/{self.case_id}/issues", json={
            "title": "Jurisdiction", "issue_type": "procedural",
        }, headers=_headers())
        resp = client.get(f"/cases/{self.case_id}/issues", headers=_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_issue_on_nonexistent_case(self):
        resp = client.post("/cases/99999/issues", json={
            "title": "test", "issue_type": "substantive",
        }, headers=_headers())
        assert resp.status_code == 404


class TestStrategyNote:
    def setup_method(self):
        self.case_id = _create_case("Notes Test")

    def test_create_note(self):
        resp = client.post(f"/cases/{self.case_id}/notes", json={
            "title": "Initial assessment",
            "content": "Strong position on liability. Damages calculation needs expert.",
        }, headers=_headers())
        assert resp.status_code == 201
        assert resp.json()["title"] == "Initial assessment"

    def test_list_notes(self):
        client.post(f"/cases/{self.case_id}/notes", json={
            "title": "Note 1", "content": "First observation",
        }, headers=_headers())
        resp = client.get(f"/cases/{self.case_id}/notes", headers=_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_note_on_nonexistent_case(self):
        resp = client.post("/cases/99999/notes", json={
            "title": "test", "content": "test",
        }, headers=_headers())
        assert resp.status_code == 404


class TestAnalysisArtifact:
    def setup_method(self):
        self.case_id = _create_case("Artifacts Test")

    def test_create_artifact(self):
        resp = client.post(f"/cases/{self.case_id}/artifacts", json={
            "artifact_type": "case_summary",
            "title": "Preliminary Case Assessment",
            "content": "Based on available evidence, the plaintiff has a strong claim...",
            "status": "draft",
        }, headers=_headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["artifact_type"] == "case_summary"
        assert data["status"] == "draft"

    def test_artifact_default_status_is_draft(self):
        resp = client.post(f"/cases/{self.case_id}/artifacts", json={
            "artifact_type": "memo",
            "title": "Research Memo",
            "content": "Applicable precedent includes...",
        }, headers=_headers())
        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"

    def test_artifact_status_final(self):
        resp = client.post(f"/cases/{self.case_id}/artifacts", json={
            "artifact_type": "brief",
            "title": "Final Brief",
            "content": "This brief addresses...",
            "status": "final",
        }, headers=_headers())
        assert resp.status_code == 201
        assert resp.json()["status"] == "final"

    def test_list_artifacts(self):
        client.post(f"/cases/{self.case_id}/artifacts", json={
            "artifact_type": "note",
            "title": "Test Artifact",
            "content": "Content here",
        }, headers=_headers())
        resp = client.get(f"/cases/{self.case_id}/artifacts", headers=_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_artifact_on_nonexistent_case(self):
        resp = client.post("/cases/99999/artifacts", json={
            "artifact_type": "memo", "title": "test", "content": "test",
        }, headers=_headers())
        assert resp.status_code == 404


class TestEventEmission:
    """Verify that CRUD operations emit events to the event table."""

    def setup_method(self):
        resp = client.post("/cases", json={
            "title": "Event Emission Test",
            "case_type": "test",
        }, headers=_headers())
        self.case_id = resp.json()["id"]

    def test_case_creation_emits_event(self):
        db = db_module.get_db()
        row = db.execute(
            "SELECT * FROM events WHERE event_type = 'case.created' AND entity_id = ?",
            (self.case_id,),
        ).fetchone()
        assert row is not None
        assert row["entity_type"] == "case"

    def test_child_entity_emits_event(self):
        resp = client.post(f"/cases/{self.case_id}/entities", json={
            "name": "Test Person", "role": "witness",
        }, headers=_headers())
        entity_id = resp.json()["id"]

        db = db_module.get_db()
        row = db.execute(
            "SELECT * FROM events WHERE event_type = 'entity.created' AND entity_id = ?",
            (entity_id,),
        ).fetchone()
        assert row is not None


class TestFullCircuit:
    """End-to-end: create case with all entity types, query everything back."""

    def test_full_circuit(self):
        h = _headers()
        cid = _create_case("Full Circuit Test", "civil")

        client.post(f"/cases/{cid}/entities", json={
            "name": "Jane Doe", "role": "plaintiff",
        }, headers=h)
        client.post(f"/cases/{cid}/timeline", json={
            "event_date": "2024-06-01", "description": "Incident occurred",
            "confidence": "medium",
        }, headers=h)
        client.post(f"/cases/{cid}/evidence", json={
            "title": "Police Report", "evidence_type": "official_document",
        }, headers=h)
        client.post(f"/cases/{cid}/issues", json={
            "title": "Negligence standard", "issue_type": "substantive",
        }, headers=h)
        client.post(f"/cases/{cid}/notes", json={
            "title": "Strategy", "content": "Focus on duty of care",
        }, headers=h)
        client.post(f"/cases/{cid}/artifacts", json={
            "artifact_type": "case_map",
            "title": "Initial Case Map",
            "content": "Parties: Jane Doe (plaintiff) v. ...",
        }, headers=h)

        assert len(client.get(f"/cases/{cid}/entities", headers=h).json()) == 1
        assert len(client.get(f"/cases/{cid}/timeline", headers=h).json()) == 1
        assert len(client.get(f"/cases/{cid}/evidence", headers=h).json()) == 1
        assert len(client.get(f"/cases/{cid}/issues", headers=h).json()) == 1
        assert len(client.get(f"/cases/{cid}/notes", headers=h).json()) == 1
        assert len(client.get(f"/cases/{cid}/artifacts", headers=h).json()) == 1

        fetched = client.get(f"/cases/{cid}", headers=h).json()
        assert fetched["title"] == "Full Circuit Test"


# ============================================================
# Source-grounding: Documents and Evidence Chunks
# ============================================================

def _create_document(case_id, title="Test Document", document_type="police_report"):
    resp = client.post(f"/cases/{case_id}/documents", json={
        "title": title,
        "document_type": document_type,
        "source_ref": f"/evidence/{title.lower().replace(' ', '_')}.pdf",
    }, headers=_headers())
    assert resp.status_code == 201
    return resp.json()["id"]


class TestDocument:
    def setup_method(self):
        self.case_id = _create_case("Document Test")

    def test_create_document(self):
        resp = client.post(f"/cases/{self.case_id}/documents", json={
            "title": "Arrest Report",
            "document_type": "police_report",
            "source_ref": "/evidence/arrest_report.pdf",
            "source_hash": "sha256:abc123",
            "notes": "Obtained via discovery 2024-01-10",
        }, headers=_headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Arrest Report"
        assert data["document_type"] == "police_report"
        assert data["source_ref"] == "/evidence/arrest_report.pdf"
        assert data["source_hash"] == "sha256:abc123"
        assert data["notes"] == "Obtained via discovery 2024-01-10"
        assert data["case_id"] == self.case_id
        assert "created_at" in data
        assert "imported_at" in data

    def test_create_document_minimal_fields(self):
        resp = client.post(f"/cases/{self.case_id}/documents", json={
            "title": "Witness Statement",
            "document_type": "statement",
        }, headers=_headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_ref"] is None
        assert data["source_hash"] is None
        assert data["notes"] is None

    def test_create_document_nonexistent_case(self):
        resp = client.post("/cases/99999/documents", json={
            "title": "Ghost Doc", "document_type": "unknown",
        }, headers=_headers())
        assert resp.status_code == 404

    def test_list_documents_scoped_to_case(self):
        other_case = _create_case("Other Case For Docs")
        _create_document(self.case_id, "Doc A")
        _create_document(other_case, "Doc B")

        resp = client.get(f"/cases/{self.case_id}/documents", headers=_headers())
        assert resp.status_code == 200
        titles = [d["title"] for d in resp.json()]
        assert "Doc A" in titles
        assert "Doc B" not in titles

    def test_get_document_in_correct_case(self):
        doc_id = _create_document(self.case_id, "Retrievable Doc")
        resp = client.get(
            f"/cases/{self.case_id}/documents/{doc_id}", headers=_headers()
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Retrievable Doc"

    def test_get_document_through_wrong_case_returns_404(self):
        other_case = _create_case("Wrong Case")
        doc_id = _create_document(self.case_id, "Case A Doc")

        resp = client.get(
            f"/cases/{other_case}/documents/{doc_id}", headers=_headers()
        )
        assert resp.status_code == 404


class TestEvidenceChunk:
    def setup_method(self):
        self.case_id = _create_case("Chunk Test")
        self.doc_id = _create_document(self.case_id, "Source Doc")

    def test_create_chunk_with_full_metadata(self):
        resp = client.post(f"/cases/{self.case_id}/chunks", json={
            "document_id": self.doc_id,
            "text": "The defendant was observed leaving the premises at 22:15.",
            "page_from": 3,
            "page_to": 3,
            "location_label": "paragraph 2",
            "timestamp_ref": "2024-01-15T22:15:00",
        }, headers=_headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["text"] == "The defendant was observed leaving the premises at 22:15."
        assert data["page_from"] == 3
        assert data["page_to"] == 3
        assert data["location_label"] == "paragraph 2"
        assert data["timestamp_ref"] == "2024-01-15T22:15:00"
        assert data["case_id"] == self.case_id
        assert data["document_id"] == self.doc_id

    def test_create_chunk_minimal_fields(self):
        resp = client.post(f"/cases/{self.case_id}/chunks", json={
            "document_id": self.doc_id,
            "text": "Minimal chunk text",
        }, headers=_headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["page_from"] is None
        assert data["page_to"] is None
        assert data["location_label"] is None
        assert data["timestamp_ref"] is None

    def test_create_chunk_nonexistent_case(self):
        resp = client.post("/cases/99999/chunks", json={
            "document_id": self.doc_id,
            "text": "Ghost chunk",
        }, headers=_headers())
        assert resp.status_code == 404

    def test_create_chunk_nonexistent_document(self):
        resp = client.post(f"/cases/{self.case_id}/chunks", json={
            "document_id": 99999,
            "text": "Orphan chunk",
        }, headers=_headers())
        assert resp.status_code == 404

    def test_create_chunk_document_case_mismatch(self):
        """Chunk's case_id must match the document's case_id."""
        other_case = _create_case("Mismatch Case")
        resp = client.post(f"/cases/{other_case}/chunks", json={
            "document_id": self.doc_id,
            "text": "This should be rejected",
        }, headers=_headers())
        assert resp.status_code == 404
        assert "not found in case" in resp.json()["detail"]

    def test_list_chunks_by_case(self):
        other_case = _create_case("Other Chunk Case")
        other_doc = _create_document(other_case, "Other Doc")

        client.post(f"/cases/{self.case_id}/chunks", json={
            "document_id": self.doc_id, "text": "Case A chunk",
        }, headers=_headers())
        client.post(f"/cases/{other_case}/chunks", json={
            "document_id": other_doc, "text": "Case B chunk",
        }, headers=_headers())

        resp = client.get(f"/cases/{self.case_id}/chunks", headers=_headers())
        assert resp.status_code == 200
        texts = [c["text"] for c in resp.json()]
        assert "Case A chunk" in texts
        assert "Case B chunk" not in texts

    def test_list_chunks_by_document(self):
        doc2 = _create_document(self.case_id, "Second Doc")

        client.post(f"/cases/{self.case_id}/chunks", json={
            "document_id": self.doc_id, "text": "From doc 1",
        }, headers=_headers())
        client.post(f"/cases/{self.case_id}/chunks", json={
            "document_id": doc2, "text": "From doc 2",
        }, headers=_headers())

        resp = client.get(
            f"/cases/{self.case_id}/documents/{self.doc_id}/chunks", headers=_headers()
        )
        assert resp.status_code == 200
        texts = [c["text"] for c in resp.json()]
        assert "From doc 1" in texts
        assert "From doc 2" not in texts

    def test_list_chunks_wrong_case_returns_404(self):
        other_case = _create_case("Wrong Chunk Case")
        resp = client.get(
            f"/cases/{other_case}/documents/{self.doc_id}/chunks", headers=_headers()
        )
        assert resp.status_code == 404

    def test_get_chunk_in_correct_case(self):
        resp = client.post(f"/cases/{self.case_id}/chunks", json={
            "document_id": self.doc_id, "text": "Specific chunk",
        }, headers=_headers())
        chunk_id = resp.json()["id"]

        resp = client.get(
            f"/cases/{self.case_id}/chunks/{chunk_id}", headers=_headers()
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == "Specific chunk"

    def test_get_chunk_through_wrong_case_returns_404(self):
        resp = client.post(f"/cases/{self.case_id}/chunks", json={
            "document_id": self.doc_id, "text": "Isolated chunk",
        }, headers=_headers())
        chunk_id = resp.json()["id"]

        other_case = _create_case("Wrong Chunk Get Case")
        resp = client.get(
            f"/cases/{other_case}/chunks/{chunk_id}", headers=_headers()
        )
        assert resp.status_code == 404


class TestSourceGroundingEvents:
    """Verify audit events for document and chunk creation."""

    def setup_method(self):
        self.case_id = _create_case("Event Grounding Test")

    def test_document_creation_emits_event(self):
        doc_id = _create_document(self.case_id, "Audited Doc")
        db = db_module.get_db()
        row = db.execute(
            "SELECT * FROM events WHERE event_type = 'document.created' AND entity_id = ?",
            (doc_id,),
        ).fetchone()
        assert row is not None
        assert row["entity_type"] == "document"

    def test_chunk_creation_emits_event(self):
        doc_id = _create_document(self.case_id, "Chunk Audit Doc")
        resp = client.post(f"/cases/{self.case_id}/chunks", json={
            "document_id": doc_id, "text": "Audited chunk text",
        }, headers=_headers())
        chunk_id = resp.json()["id"]

        db = db_module.get_db()
        row = db.execute(
            "SELECT * FROM events WHERE event_type = 'chunk.created' AND entity_id = ?",
            (chunk_id,),
        ).fetchone()
        assert row is not None
        assert row["entity_type"] == "evidence_chunk"


# ============================================================
# Source-anchored cross-reference links
# ============================================================

def _setup_linkable_case():
    """Create a case with a document and a chunk. Return (case_id, chunk_id)."""
    case_id = _create_case("Link Test")
    doc_id = _create_document(case_id, "Link Doc")
    resp = client.post(f"/cases/{case_id}/chunks", json={
        "document_id": doc_id,
        "text": "The defendant was seen at the location.",
        "page_from": 5,
        "page_to": 5,
        "location_label": "paragraph 3",
        "timestamp_ref": "2024-03-15T14:30:00",
    }, headers=_headers())
    return case_id, resp.json()["id"], doc_id


class TestTimelineEventLinks:
    def setup_method(self):
        self.case_id, self.chunk_id, self.doc_id = _setup_linkable_case()
        resp = client.post(f"/cases/{self.case_id}/timeline", json={
            "event_date": "2024-03-15", "description": "Defendant at location",
        }, headers=_headers())
        self.event_id = resp.json()["id"]

    def test_link_chunk_to_timeline_event(self):
        resp = client.post(
            f"/cases/{self.case_id}/timeline/{self.event_id}/links",
            json={"chunk_id": self.chunk_id, "relation_type": "supports"},
            headers=_headers(),
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "linked"

    def test_list_linked_chunks(self):
        client.post(
            f"/cases/{self.case_id}/timeline/{self.event_id}/links",
            json={"chunk_id": self.chunk_id},
            headers=_headers(),
        )
        resp = client.get(
            f"/cases/{self.case_id}/timeline/{self.event_id}/links",
            headers=_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        chunk = data[0]
        assert chunk["chunk_id"] == self.chunk_id
        assert chunk["text"] == "The defendant was seen at the location."
        assert chunk["page_from"] == 5
        assert chunk["location_label"] == "paragraph 3"
        assert chunk["timestamp_ref"] == "2024-03-15T14:30:00"
        assert chunk["document_title"] == "Link Doc"

    def test_reject_cross_case_chunk_link(self):
        other_case, other_chunk, _ = _setup_linkable_case()
        resp = client.post(
            f"/cases/{self.case_id}/timeline/{self.event_id}/links",
            json={"chunk_id": other_chunk},
            headers=_headers(),
        )
        assert resp.status_code == 404
        assert "Chunk" in resp.json()["detail"]

    def test_reject_nonexistent_chunk(self):
        resp = client.post(
            f"/cases/{self.case_id}/timeline/{self.event_id}/links",
            json={"chunk_id": 99999},
            headers=_headers(),
        )
        assert resp.status_code == 404

    def test_reject_nonexistent_event(self):
        resp = client.post(
            f"/cases/{self.case_id}/timeline/99999/links",
            json={"chunk_id": self.chunk_id},
            headers=_headers(),
        )
        assert resp.status_code == 404

    def test_reject_duplicate_link(self):
        client.post(
            f"/cases/{self.case_id}/timeline/{self.event_id}/links",
            json={"chunk_id": self.chunk_id},
            headers=_headers(),
        )
        resp = client.post(
            f"/cases/{self.case_id}/timeline/{self.event_id}/links",
            json={"chunk_id": self.chunk_id},
            headers=_headers(),
        )
        assert resp.status_code == 409

    def test_no_cross_case_link_retrieval(self):
        other_case = _create_case("Wrong Link Case")
        resp = client.get(
            f"/cases/{other_case}/timeline/{self.event_id}/links",
            headers=_headers(),
        )
        assert resp.status_code == 404


class TestLegalIssueLinks:
    def setup_method(self):
        self.case_id, self.chunk_id, _ = _setup_linkable_case()
        resp = client.post(f"/cases/{self.case_id}/issues", json={
            "title": "Alibi question", "issue_type": "factual",
        }, headers=_headers())
        self.issue_id = resp.json()["id"]

    def test_link_and_list(self):
        resp = client.post(
            f"/cases/{self.case_id}/issues/{self.issue_id}/links",
            json={"chunk_id": self.chunk_id, "relation_type": "contradicts"},
            headers=_headers(),
        )
        assert resp.status_code == 201

        resp = client.get(
            f"/cases/{self.case_id}/issues/{self.issue_id}/links",
            headers=_headers(),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["relation_type"] == "contradicts"

    def test_reject_cross_case(self):
        other_case, other_chunk, _ = _setup_linkable_case()
        resp = client.post(
            f"/cases/{self.case_id}/issues/{self.issue_id}/links",
            json={"chunk_id": other_chunk},
            headers=_headers(),
        )
        assert resp.status_code == 404


class TestStrategyNoteLinks:
    def setup_method(self):
        self.case_id, self.chunk_id, _ = _setup_linkable_case()
        resp = client.post(f"/cases/{self.case_id}/notes", json={
            "title": "Defense angle", "content": "Challenge witness placement",
        }, headers=_headers())
        self.note_id = resp.json()["id"]

    def test_link_and_list(self):
        resp = client.post(
            f"/cases/{self.case_id}/notes/{self.note_id}/links",
            json={"chunk_id": self.chunk_id},
            headers=_headers(),
        )
        assert resp.status_code == 201

        resp = client.get(
            f"/cases/{self.case_id}/notes/{self.note_id}/links",
            headers=_headers(),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["text"] == "The defendant was seen at the location."

    def test_reject_cross_case(self):
        other_case, other_chunk, _ = _setup_linkable_case()
        resp = client.post(
            f"/cases/{self.case_id}/notes/{self.note_id}/links",
            json={"chunk_id": other_chunk},
            headers=_headers(),
        )
        assert resp.status_code == 404


class TestAnalysisArtifactLinks:
    def setup_method(self):
        self.case_id, self.chunk_id, _ = _setup_linkable_case()
        resp = client.post(f"/cases/{self.case_id}/artifacts", json={
            "artifact_type": "memo", "title": "Location analysis",
            "content": "Evidence places defendant at scene",
        }, headers=_headers())
        self.artifact_id = resp.json()["id"]

    def test_link_and_list(self):
        resp = client.post(
            f"/cases/{self.case_id}/artifacts/{self.artifact_id}/links",
            json={"chunk_id": self.chunk_id, "relation_type": "cites"},
            headers=_headers(),
        )
        assert resp.status_code == 201

        resp = client.get(
            f"/cases/{self.case_id}/artifacts/{self.artifact_id}/links",
            headers=_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["relation_type"] == "cites"
        assert data[0]["source_ref"] is not None  # joined from documents

    def test_reject_cross_case(self):
        other_case, other_chunk, _ = _setup_linkable_case()
        resp = client.post(
            f"/cases/{self.case_id}/artifacts/{self.artifact_id}/links",
            json={"chunk_id": other_chunk},
            headers=_headers(),
        )
        assert resp.status_code == 404

    def test_reject_duplicate(self):
        client.post(
            f"/cases/{self.case_id}/artifacts/{self.artifact_id}/links",
            json={"chunk_id": self.chunk_id},
            headers=_headers(),
        )
        resp = client.post(
            f"/cases/{self.case_id}/artifacts/{self.artifact_id}/links",
            json={"chunk_id": self.chunk_id},
            headers=_headers(),
        )
        assert resp.status_code == 409


class TestLinkAuditEvents:
    def setup_method(self):
        self.case_id, self.chunk_id, _ = _setup_linkable_case()

    def test_timeline_link_emits_event(self):
        resp = client.post(f"/cases/{self.case_id}/timeline", json={
            "event_date": "2024-01-01", "description": "Audit link test",
        }, headers=_headers())
        event_id = resp.json()["id"]

        resp = client.post(
            f"/cases/{self.case_id}/timeline/{event_id}/links",
            json={"chunk_id": self.chunk_id},
            headers=_headers(),
        )
        link_id = resp.json()["id"]

        db = db_module.get_db()
        row = db.execute(
            "SELECT * FROM events WHERE event_type = 'link.timeline_event_chunk.created' AND entity_id = ?",
            (link_id,),
        ).fetchone()
        assert row is not None

    def test_artifact_link_emits_event(self):
        resp = client.post(f"/cases/{self.case_id}/artifacts", json={
            "artifact_type": "memo", "title": "Audit test",
            "content": "Content",
        }, headers=_headers())
        artifact_id = resp.json()["id"]

        resp = client.post(
            f"/cases/{self.case_id}/artifacts/{artifact_id}/links",
            json={"chunk_id": self.chunk_id},
            headers=_headers(),
        )
        link_id = resp.json()["id"]

        db = db_module.get_db()
        row = db.execute(
            "SELECT * FROM events WHERE event_type = 'link.analysis_artifact_chunk.created' AND entity_id = ?",
            (link_id,),
        ).fetchone()
        assert row is not None


# ============================================================
# Case coverage / source-grounding summary
# ============================================================

class TestCaseCoverage:
    """Test the read-only coverage surface."""

    def setup_method(self):
        h = _headers()
        self.case_id = _create_case("Coverage Test", "criminal")

        # Create a document + chunk for linking
        self.doc_id = _create_document(self.case_id, "Coverage Doc")
        resp = client.post(f"/cases/{self.case_id}/chunks", json={
            "document_id": self.doc_id, "text": "Key evidence text",
            "page_from": 1, "page_to": 1,
        }, headers=h)
        self.chunk_id = resp.json()["id"]

        # Create 2 timeline events — link only one
        resp = client.post(f"/cases/{self.case_id}/timeline", json={
            "event_date": "2024-01-01", "description": "Linked event",
        }, headers=h)
        self.linked_te = resp.json()["id"]
        resp = client.post(f"/cases/{self.case_id}/timeline", json={
            "event_date": "2024-01-02", "description": "Unlinked event",
        }, headers=h)
        self.unlinked_te = resp.json()["id"]
        client.post(
            f"/cases/{self.case_id}/timeline/{self.linked_te}/links",
            json={"chunk_id": self.chunk_id}, headers=h,
        )

        # Create 2 legal issues — link only one
        resp = client.post(f"/cases/{self.case_id}/issues", json={
            "title": "Linked issue", "issue_type": "factual",
        }, headers=h)
        self.linked_li = resp.json()["id"]
        resp = client.post(f"/cases/{self.case_id}/issues", json={
            "title": "Unlinked issue", "issue_type": "procedural",
        }, headers=h)
        self.unlinked_li = resp.json()["id"]
        client.post(
            f"/cases/{self.case_id}/issues/{self.linked_li}/links",
            json={"chunk_id": self.chunk_id}, headers=h,
        )

        # Create 1 strategy note — unlinked
        resp = client.post(f"/cases/{self.case_id}/notes", json={
            "title": "Ungrounded note", "content": "Speculation without source",
        }, headers=h)
        self.unlinked_sn = resp.json()["id"]

        # Create 1 artifact — linked
        resp = client.post(f"/cases/{self.case_id}/artifacts", json={
            "artifact_type": "memo", "title": "Grounded memo",
            "content": "Analysis based on evidence",
        }, headers=h)
        self.linked_aa = resp.json()["id"]
        client.post(
            f"/cases/{self.case_id}/artifacts/{self.linked_aa}/links",
            json={"chunk_id": self.chunk_id}, headers=h,
        )

    def test_coverage_returns_correct_counts(self):
        resp = client.get(f"/cases/{self.case_id}/coverage", headers=_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["case_id"] == self.case_id
        assert data["title"] == "Coverage Test"
        assert data["documents_count"] == 1
        assert data["evidence_chunks_count"] == 1

    def test_timeline_event_coverage(self):
        resp = client.get(f"/cases/{self.case_id}/coverage", headers=_headers())
        te = resp.json()["timeline_events"]
        assert te["total"] == 2
        assert te["linked"] == 1
        assert te["unlinked"] == 1
        assert len(te["unlinked_items"]) == 1
        assert te["unlinked_items"][0]["id"] == self.unlinked_te
        assert te["unlinked_items"][0]["label"] == "Unlinked event"

    def test_legal_issue_coverage(self):
        resp = client.get(f"/cases/{self.case_id}/coverage", headers=_headers())
        li = resp.json()["legal_issues"]
        assert li["total"] == 2
        assert li["linked"] == 1
        assert li["unlinked"] == 1
        assert len(li["unlinked_items"]) == 1
        assert li["unlinked_items"][0]["id"] == self.unlinked_li
        assert li["unlinked_items"][0]["label"] == "Unlinked issue"

    def test_strategy_note_coverage(self):
        resp = client.get(f"/cases/{self.case_id}/coverage", headers=_headers())
        sn = resp.json()["strategy_notes"]
        assert sn["total"] == 1
        assert sn["linked"] == 0
        assert sn["unlinked"] == 1
        assert sn["unlinked_items"][0]["id"] == self.unlinked_sn

    def test_analysis_artifact_coverage(self):
        resp = client.get(f"/cases/{self.case_id}/coverage", headers=_headers())
        aa = resp.json()["analysis_artifacts"]
        assert aa["total"] == 1
        assert aa["linked"] == 1
        assert aa["unlinked"] == 0
        assert aa["unlinked_items"] == []

    def test_empty_case_returns_all_zeros(self):
        empty_case = _create_case("Empty Case")
        resp = client.get(f"/cases/{empty_case}/coverage", headers=_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["documents_count"] == 0
        assert data["evidence_chunks_count"] == 0
        assert data["timeline_events"]["total"] == 0
        assert data["legal_issues"]["total"] == 0
        assert data["strategy_notes"]["total"] == 0
        assert data["analysis_artifacts"]["total"] == 0

    def test_no_cross_case_leakage(self):
        other_case = _create_case("Isolated Case")
        resp = client.get(f"/cases/{other_case}/coverage", headers=_headers())
        data = resp.json()
        # Other case has nothing — must not see this case's data
        assert data["documents_count"] == 0
        assert data["evidence_chunks_count"] == 0
        assert data["timeline_events"]["total"] == 0

    def test_nonexistent_case_returns_404(self):
        resp = client.get("/cases/99999/coverage", headers=_headers())
        assert resp.status_code == 404


# ============================================================
# Case audit surface
# ============================================================

class TestCaseAudit:
    """Test the read-only case-scoped audit event surface."""

    def setup_method(self):
        h = _headers()
        # Create a case — generates case.created event
        self.case_id = _create_case("Audit Test Case", "criminal")

        # Add a person entity — generates entity.created event
        client.post(f"/cases/{self.case_id}/entities", json={
            "name": "Jane Witness", "role": "witness",
        }, headers=h)

        # Add a timeline event — generates timeline.created event
        resp = client.post(f"/cases/{self.case_id}/timeline", json={
            "event_date": "2024-06-01", "description": "Incident",
        }, headers=h)
        self.event_id = resp.json()["id"]

        # Add a document + chunk — generates document.created, chunk.created
        self.doc_id = _create_document(self.case_id, "Audit Doc")
        resp = client.post(f"/cases/{self.case_id}/chunks", json={
            "document_id": self.doc_id, "text": "Audit chunk text",
        }, headers=h)
        self.chunk_id = resp.json()["id"]

        # Link timeline event to chunk — generates link event
        client.post(
            f"/cases/{self.case_id}/timeline/{self.event_id}/links",
            json={"chunk_id": self.chunk_id}, headers=h,
        )

    def test_audit_returns_case_creation_event(self):
        resp = client.get(f"/cases/{self.case_id}/audit", headers=_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["case_id"] == self.case_id
        types = [e["event_type"] for e in data["events"]]
        assert "case.created" in types

    def test_audit_returns_child_entity_events(self):
        resp = client.get(f"/cases/{self.case_id}/audit", headers=_headers())
        types = [e["event_type"] for e in resp.json()["events"]]
        assert "entity.created" in types
        assert "timeline.created" in types

    def test_audit_returns_source_grounding_events(self):
        resp = client.get(f"/cases/{self.case_id}/audit", headers=_headers())
        types = [e["event_type"] for e in resp.json()["events"]]
        assert "document.created" in types
        assert "chunk.created" in types

    def test_audit_returns_link_events(self):
        resp = client.get(f"/cases/{self.case_id}/audit", headers=_headers())
        types = [e["event_type"] for e in resp.json()["events"]]
        assert "link.timeline_event_chunk.created" in types

    def test_audit_total_event_count(self):
        resp = client.get(f"/cases/{self.case_id}/audit", headers=_headers())
        data = resp.json()
        # case.created + entity.created + timeline.created + document.created
        # + chunk.created + link.timeline_event_chunk.created = 6
        assert data["total_events"] == 6

    def test_audit_events_are_chronologically_ordered(self):
        resp = client.get(f"/cases/{self.case_id}/audit", headers=_headers())
        events = resp.json()["events"]
        timestamps = [e["created_at"] for e in events]
        assert timestamps == sorted(timestamps)

    def test_audit_event_fields_are_present(self):
        resp = client.get(f"/cases/{self.case_id}/audit", headers=_headers())
        event = resp.json()["events"][0]
        assert "id" in event
        assert "event_type" in event
        assert "entity_type" in event
        assert "entity_id" in event
        assert "origin_module" in event
        assert "payload" in event
        assert "created_at" in event

    def test_no_cross_case_leakage(self):
        other_case = _create_case("Isolated Audit Case")
        resp = client.get(f"/cases/{other_case}/audit", headers=_headers())
        data = resp.json()
        # Other case should only have its own case.created event
        assert data["total_events"] == 1
        assert data["events"][0]["event_type"] == "case.created"
        assert data["events"][0]["entity_id"] == other_case

    def test_nonexistent_case_returns_404(self):
        resp = client.get("/cases/99999/audit", headers=_headers())
        assert resp.status_code == 404


# ============================================================
# Entity update (PATCH) endpoints
# ============================================================

class TestUpdateTimelineEvent:
    def setup_method(self):
        h = _headers()
        self.case_id = _create_case("TE Update Test")
        resp = client.post(f"/cases/{self.case_id}/timeline", json={
            "event_date": "2024-01-01", "description": "Original description",
            "confidence": "low",
        }, headers=h)
        self.event_id = resp.json()["id"]

    def test_partial_update(self):
        resp = client.patch(f"/cases/{self.case_id}/timeline/{self.event_id}", json={
            "description": "Updated description",
        }, headers=_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Updated description"
        # Unspecified fields preserved
        assert data["event_date"] == "2024-01-01"
        assert data["confidence"] == "low"

    def test_update_confidence(self):
        resp = client.patch(f"/cases/{self.case_id}/timeline/{self.event_id}", json={
            "confidence": "high",
        }, headers=_headers())
        assert resp.status_code == 200
        assert resp.json()["confidence"] == "high"

    def test_cross_case_rejected(self):
        other_case = _create_case("Wrong TE Case")
        resp = client.patch(f"/cases/{other_case}/timeline/{self.event_id}", json={
            "description": "Hijack",
        }, headers=_headers())
        assert resp.status_code == 404

    def test_nonexistent_event_rejected(self):
        resp = client.patch(f"/cases/{self.case_id}/timeline/99999", json={
            "description": "Ghost",
        }, headers=_headers())
        assert resp.status_code == 404

    def test_empty_update_returns_unchanged(self):
        resp = client.patch(f"/cases/{self.case_id}/timeline/{self.event_id}", json={},
                            headers=_headers())
        assert resp.status_code == 200
        assert resp.json()["description"] == "Original description"


class TestUpdateLegalIssue:
    def setup_method(self):
        h = _headers()
        self.case_id = _create_case("LI Update Test")
        resp = client.post(f"/cases/{self.case_id}/issues", json={
            "title": "Original title", "issue_type": "procedural",
        }, headers=h)
        self.issue_id = resp.json()["id"]
        self.original_updated_at = resp.json()["updated_at"]

    def test_partial_update_with_updated_at(self):
        resp = client.patch(f"/cases/{self.case_id}/issues/{self.issue_id}", json={
            "analysis": "New analysis text",
        }, headers=_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["analysis"] == "New analysis text"
        assert data["title"] == "Original title"  # preserved
        assert data["updated_at"] > self.original_updated_at

    def test_update_status(self):
        resp = client.patch(f"/cases/{self.case_id}/issues/{self.issue_id}", json={
            "status": "resolved",
        }, headers=_headers())
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    def test_cross_case_rejected(self):
        other_case = _create_case("Wrong LI Case")
        resp = client.patch(f"/cases/{other_case}/issues/{self.issue_id}", json={
            "title": "Hijack",
        }, headers=_headers())
        assert resp.status_code == 404


class TestUpdateStrategyNote:
    def setup_method(self):
        h = _headers()
        self.case_id = _create_case("SN Update Test")
        resp = client.post(f"/cases/{self.case_id}/notes", json={
            "title": "Original note", "content": "Original content",
        }, headers=h)
        self.note_id = resp.json()["id"]

    def test_partial_update(self):
        resp = client.patch(f"/cases/{self.case_id}/notes/{self.note_id}", json={
            "content": "Revised content",
        }, headers=_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "Revised content"
        assert data["title"] == "Original note"  # preserved

    def test_cross_case_rejected(self):
        other_case = _create_case("Wrong SN Case")
        resp = client.patch(f"/cases/{other_case}/notes/{self.note_id}", json={
            "title": "Hijack",
        }, headers=_headers())
        assert resp.status_code == 404


class TestUpdateAnalysisArtifact:
    def setup_method(self):
        h = _headers()
        self.case_id = _create_case("AA Update Test")
        resp = client.post(f"/cases/{self.case_id}/artifacts", json={
            "artifact_type": "memo", "title": "Draft memo",
            "content": "Initial content", "status": "draft",
        }, headers=h)
        self.artifact_id = resp.json()["id"]
        self.original_updated_at = resp.json()["updated_at"]

    def test_partial_update_with_updated_at(self):
        resp = client.patch(f"/cases/{self.case_id}/artifacts/{self.artifact_id}", json={
            "content": "Revised content",
        }, headers=_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "Revised content"
        assert data["title"] == "Draft memo"  # preserved
        assert data["status"] == "draft"  # preserved
        assert data["updated_at"] > self.original_updated_at

    def test_status_draft_to_final(self):
        resp = client.patch(f"/cases/{self.case_id}/artifacts/{self.artifact_id}", json={
            "status": "final",
        }, headers=_headers())
        assert resp.status_code == 200
        assert resp.json()["status"] == "final"

    def test_cross_case_rejected(self):
        other_case = _create_case("Wrong AA Case")
        resp = client.patch(f"/cases/{other_case}/artifacts/{self.artifact_id}", json={
            "title": "Hijack",
        }, headers=_headers())
        assert resp.status_code == 404


class TestUpdateAuditEvents:
    def setup_method(self):
        h = _headers()
        self.case_id = _create_case("Update Audit Test")
        resp = client.post(f"/cases/{self.case_id}/timeline", json={
            "event_date": "2024-01-01", "description": "Event for audit",
        }, headers=h)
        self.event_id = resp.json()["id"]

    def test_update_emits_event(self):
        client.patch(f"/cases/{self.case_id}/timeline/{self.event_id}", json={
            "description": "Updated for audit test",
        }, headers=_headers())

        db = db_module.get_db()
        row = db.execute(
            "SELECT * FROM events WHERE event_type = 'timeline_event.updated' AND entity_id = ?",
            (self.event_id,),
        ).fetchone()
        assert row is not None
        assert row["entity_type"] == "timeline_event"

    def test_update_event_appears_in_case_audit(self):
        client.patch(f"/cases/{self.case_id}/timeline/{self.event_id}", json={
            "description": "For audit surface",
        }, headers=_headers())

        resp = client.get(f"/cases/{self.case_id}/audit", headers=_headers())
        types = [e["event_type"] for e in resp.json()["events"]]
        assert "timeline_event.updated" in types
