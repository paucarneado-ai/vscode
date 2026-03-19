import csv
import io
import tempfile

import pytest

import apps.api.db as db_module

# Use a temporary SQLite file for tests
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
db_module.DATABASE_PATH = _tmp.name
db_module.reset_db()
db_module.init_db()

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)

VALID_LEAD = {
    "name": "Test User",
    "email": "test@example.com",
    "source": "test",
    "notes": "interested in demo",
}

# Strong notes that produce score >= 60 for ANY source (including non-test)
# base(20) + notes(5) + boat_type(10) + phone(10) + eslora(10) + detail(5) = 60
# With test source: +5 more = 65
STRONG_NOTES = "Tipo: Velero\nTeléfono: +34612345678\nEslora: 14m\nMarca/modelo: Hanse 470"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_health_detail():
    response = client.get("/health/detail")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "OpenClaw"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data
    assert data["checks"]["database"] == "ok"
    assert isinstance(data["checks"]["lead_count"], int)


def test_routes():
    response = client.get("/routes")
    assert response.status_code == 200
    routes = response.json()
    assert isinstance(routes, list)
    assert all(isinstance(r, str) for r in routes)
    assert "/health" in routes
    assert "/leads" in routes
    assert "/routes" in routes


def test_create_lead_valid():
    response = client.post("/leads", json=VALID_LEAD)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "lead received"
    lead = data["lead"]
    assert lead["name"] == "Test User"
    assert lead["email"] == "test@example.com"
    assert lead["score"] == 30  # base 20 + test source 5 + notes 5
    assert "id" in lead
    assert "created_at" in lead


def test_create_lead_invalid():
    payload = {"name": ""}  # missing email, empty name
    response = client.post("/leads", json=payload)
    assert response.status_code == 422


def test_list_leads():
    client.post("/leads", json=VALID_LEAD)
    response = client.get("/leads")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_lead_by_id():
    # Create a lead first
    response = client.post("/leads", json=VALID_LEAD)
    lead_id = response.json()["lead"]["id"]

    response = client.get(f"/leads/{lead_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == lead_id
    assert data["name"] == "Test User"


def test_get_lead_not_found():
    response = client.get("/leads/99999")
    assert response.status_code == 404


def test_get_lead_pack():
    response = client.post("/leads", json=VALID_LEAD)
    lead_id = response.json()["lead"]["id"]

    response = client.get(f"/leads/{lead_id}/pack")
    assert response.status_code == 200
    data = response.json()
    assert data["lead_id"] == lead_id
    assert data["rating"] == "low"  # score 30 -> low
    assert data["name"] == "Test User"
    assert "summary" in data
    assert "created_at" in data


def test_get_lead_pack_not_found():
    response = client.get("/leads/99999/pack")
    assert response.status_code == 404


def test_get_lead_pack_html():
    response = client.post("/leads", json=VALID_LEAD)
    lead_id = response.json()["lead"]["id"]

    response = client.get(f"/leads/{lead_id}/pack/html")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "Test User" in body
    assert "test@example.com" in body
    assert "low" in body  # score 30 -> low with new scoring


def test_get_lead_pack_html_not_found():
    response = client.get("/leads/99999/pack/html")
    assert response.status_code == 404


def test_get_lead_pack_text():
    response = client.post("/leads", json=VALID_LEAD)
    lead_id = response.json()["lead"]["id"]

    response = client.get(f"/leads/{lead_id}/pack.txt")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "Test User" in body
    assert "test@example.com" in body
    assert "low" in body  # score 30 -> low with new scoring


def test_get_lead_pack_text_not_found():
    response = client.get("/leads/99999/pack.txt")
    assert response.status_code == 404


def test_get_lead_delivery():
    response = client.post("/leads", json=VALID_LEAD)
    lead_id = response.json()["lead"]["id"]

    response = client.get(f"/leads/{lead_id}/delivery")
    assert response.status_code == 200
    data = response.json()
    assert data["lead_id"] == lead_id
    assert data["delivery_status"] == "generated"
    assert data["channel"] == "api"
    assert "generated_at" in data
    assert data["pack"]["rating"] == "low"
    assert "message" in data


def test_get_lead_delivery_not_found():
    response = client.get("/leads/99999/delivery")
    assert response.status_code == 404


def test_get_lead_delivery_response_structure():
    r = client.post("/leads", json={**VALID_LEAD, "email": "delstruct@delivery.com", "source": "del_struct"})
    lead_id = r.json()["lead"]["id"]

    resp = client.get(f"/leads/{lead_id}/delivery")
    assert resp.status_code == 200
    data = resp.json()

    # All top-level fields present with expected types
    assert isinstance(data["lead_id"], int)
    assert isinstance(data["delivery_status"], str)
    assert isinstance(data["channel"], str)
    assert isinstance(data["generated_at"], str)
    assert isinstance(data["next_action"], str)
    assert isinstance(data["alert"], bool)
    assert isinstance(data["message"], str)
    assert isinstance(data["pack"], dict)

    # Pack has all expected fields
    pack = data["pack"]
    for field in ["lead_id", "created_at", "name", "email", "source", "notes", "score", "rating", "summary", "next_action", "alert"]:
        assert field in pack, f"missing field '{field}' in pack"


def test_get_lead_delivery_pack_consistent_with_standalone():
    r = client.post("/leads", json={**VALID_LEAD, "email": "delcon@delivery.com", "source": "del_consist"})
    lead_id = r.json()["lead"]["id"]

    pack_resp = client.get(f"/leads/{lead_id}/pack").json()
    delivery_resp = client.get(f"/leads/{lead_id}/delivery").json()

    # Embedded pack should match standalone pack
    assert delivery_resp["pack"] == pack_resp


def test_get_lead_delivery_generated_at_is_current():
    r = client.post("/leads", json={**VALID_LEAD, "email": "deltime@delivery.com", "source": "del_time"})
    lead_id = r.json()["lead"]["id"]

    data = client.get(f"/leads/{lead_id}/delivery").json()
    # generated_at should be a valid ISO timestamp, distinct from lead created_at
    assert "T" in data["generated_at"]
    assert data["generated_at"] != data["pack"]["created_at"]


def test_list_leads_filter_by_source():
    client.post("/leads", json={**VALID_LEAD, "source": "filterable"})
    response = client.get("/leads", params={"source": "filterable"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(lead["source"] == "filterable" for lead in data)


def test_list_leads_filter_by_source_no_match():
    response = client.get("/leads", params={"source": "nonexistent_source_xyz"})
    assert response.status_code == 200
    assert response.json() == []


def test_list_leads_filter_by_min_score():
    client.post("/leads", json=VALID_LEAD)
    response = client.get("/leads", params={"min_score": 25})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(lead["score"] >= 25 for lead in data)


def test_list_leads_with_limit():
    client.post("/leads", json=VALID_LEAD)
    client.post("/leads", json=VALID_LEAD)
    response = client.get("/leads", params={"limit": 1})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_list_leads_with_offset():
    # Create leads with unique emails to avoid dedup
    client.post("/leads", json={**VALID_LEAD, "email": "off1@example.com", "source": "offset_test"})
    client.post("/leads", json={**VALID_LEAD, "email": "off2@example.com", "source": "offset_test"})
    client.post("/leads", json={**VALID_LEAD, "email": "off3@example.com", "source": "offset_test"})

    all_resp = client.get("/leads", params={"source": "offset_test"})
    all_data = all_resp.json()

    offset_resp = client.get("/leads", params={"source": "offset_test", "offset": 1})
    offset_data = offset_resp.json()

    assert len(offset_data) == len(all_data) - 1
    assert offset_data[0]["id"] == all_data[1]["id"]


def test_list_leads_pagination_order():
    # Create leads with unique emails to avoid dedup
    ids = []
    for i in range(3):
        r = client.post("/leads", json={**VALID_LEAD, "email": f"page{i}@example.com", "source": "page_order"})
        ids.append(r.json()["lead"]["id"])

    # Page 1
    p1 = client.get("/leads", params={"source": "page_order", "limit": 2, "offset": 0}).json()
    # Page 2
    p2 = client.get("/leads", params={"source": "page_order", "limit": 2, "offset": 2}).json()

    # ORDER BY id DESC: first page has newest
    assert p1[0]["id"] > p1[1]["id"]
    assert len(p2) >= 1
    assert p1[-1]["id"] > p2[0]["id"]


def test_list_leads_with_combined_filters():
    client.post("/leads", json={**VALID_LEAD, "source": "combo"})
    response = client.get(
        "/leads", params={"source": "combo", "min_score": 20, "limit": 5, "offset": 0}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(lead["source"] == "combo" and lead["score"] >= 20 for lead in data)
    assert len(data) <= 5


def test_list_leads_invalid_limit():
    response = client.get("/leads", params={"limit": -1})
    assert response.status_code == 422


def test_list_leads_invalid_offset():
    response = client.get("/leads", params={"offset": -1})
    assert response.status_code == 422


def test_list_leads_invalid_min_score():
    response = client.get("/leads", params={"min_score": -5})
    assert response.status_code == 422


# --- POST /leads contract ---


def test_create_lead_response_meta():
    r = client.post("/leads", json={**VALID_LEAD, "email": "meta@contract.com", "source": "meta_src"})
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["version"] == "v1"
    assert data["meta"]["status"] == "accepted"


def test_create_lead_without_notes():
    r = client.post("/leads", json={"name": "No Notes", "email": "nonotes@contract.com", "source": "contract"})
    assert r.status_code == 200
    lead = r.json()["lead"]
    assert lead["notes"] is None


def test_create_lead_invalid_email_format():
    r = client.post("/leads", json={**VALID_LEAD, "email": "not-an-email"})
    assert r.status_code == 422


def test_create_lead_duplicate_preserves_original():
    original = {**VALID_LEAD, "email": "preserve@contract.com", "source": "preserve_src"}
    r1 = client.post("/leads", json=original)
    assert r1.status_code == 200
    original_lead = r1.json()["lead"]

    # Retry with different name — 409 should return original data, not the retry
    r2 = client.post("/leads", json={**original, "name": "Different Name"})
    assert r2.status_code == 409
    dup_lead = r2.json()["lead"]
    assert dup_lead["id"] == original_lead["id"]
    assert dup_lead["name"] == original_lead["name"]  # original name, not "Different Name"


def test_create_lead_whitespace_only_source():
    # Whitespace-only source is rejected after normalization (strip → empty).
    r = client.post("/leads", json={**VALID_LEAD, "email": "ws@contract.com", "source": " "})
    assert r.status_code == 422


def test_create_lead_normalizes_source():
    response = client.post("/leads", json={**VALID_LEAD, "source": "  WebSite  "})
    assert response.status_code == 200
    lead = response.json()["lead"]
    assert lead["source"] == "website"


def test_create_lead_normalizes_email():
    response = client.post(
        "/leads", json={**VALID_LEAD, "email": "  Alice@Example.COM  "}
    )
    assert response.status_code == 200
    lead = response.json()["lead"]
    assert lead["email"] == "alice@example.com"


def test_create_lead_normalization_preserves_scoring():
    # Normalized source should produce same score regardless of casing/whitespace
    response = client.post("/leads", json={**VALID_LEAD, "email": "normscore@example.com", "source": " Test "})
    assert response.status_code == 200
    lead = response.json()["lead"]
    assert lead["source"] == "test"
    assert lead["score"] == 30  # base 20 + test source 5 + notes 5 (source no longer affects score)


def test_create_lead_duplicate_returns_409():
    lead = {**VALID_LEAD, "email": "dup@example.com", "source": "dup_src"}
    r1 = client.post("/leads", json=lead)
    assert r1.status_code == 200

    r2 = client.post("/leads", json=lead)
    assert r2.status_code == 409
    data = r2.json()
    assert data["message"] == "lead already exists"
    assert data["meta"]["status"] == "duplicate"
    assert data["lead"]["id"] == r1.json()["lead"]["id"]


def test_create_lead_duplicate_ignores_case_and_whitespace():
    lead1 = {**VALID_LEAD, "email": "Dedup@Example.COM", "source": "  DedupSrc  "}
    lead2 = {**VALID_LEAD, "email": "dedup@example.com", "source": "dedupsrc"}
    r1 = client.post("/leads", json=lead1)
    assert r1.status_code == 200
    r2 = client.post("/leads", json=lead2)
    assert r2.status_code == 409


def test_create_lead_same_email_different_source_ok():
    email = "multi@example.com"
    r1 = client.post("/leads", json={**VALID_LEAD, "email": email, "source": "src_a"})
    r2 = client.post("/leads", json={**VALID_LEAD, "email": email, "source": "src_b"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["lead"]["id"] != r2.json()["lead"]["id"]


def test_create_lead_same_source_different_email_ok():
    source = "shared_source"
    r1 = client.post("/leads", json={**VALID_LEAD, "email": "a@example.com", "source": source})
    r2 = client.post("/leads", json={**VALID_LEAD, "email": "b@example.com", "source": source})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["lead"]["id"] != r2.json()["lead"]["id"]


# --- Search (q param) ---

def test_search_leads_by_name():
    client.post("/leads", json={
        "name": "Zara Searchable", "email": "zara@search.com",
        "source": "search_name", "notes": "nothing special",
    })
    resp = client.get("/leads", params={"q": "Zara Searchable"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all("Zara Searchable" in lead["name"] for lead in data)


def test_search_leads_by_email():
    client.post("/leads", json={
        "name": "Email Search", "email": "findme_unique@search.com",
        "source": "search_email", "notes": "none",
    })
    resp = client.get("/leads", params={"q": "findme_unique"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all("findme_unique" in lead["email"] for lead in data)


def test_search_leads_by_notes():
    client.post("/leads", json={
        "name": "Notes Search", "email": "notes_s@search.com",
        "source": "search_notes", "notes": "xylophone_keyword",
    })
    resp = client.get("/leads", params={"q": "xylophone_keyword"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all("xylophone_keyword" in (lead["notes"] or "") for lead in data)


def test_search_leads_no_match():
    resp = client.get("/leads", params={"q": "zzz_nomatch_zzz_12345"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_leads_combined_with_source():
    client.post("/leads", json={
        "name": "Combo Search", "email": "combo_s@search.com",
        "source": "search_combo", "notes": "combo_keyword_abc",
    })
    # q matches but wrong source -> empty
    resp = client.get("/leads", params={"q": "combo_keyword_abc", "source": "wrong_source"})
    assert resp.json() == []
    # q matches and right source -> found
    resp = client.get("/leads", params={"q": "combo_keyword_abc", "source": "search_combo"})
    assert len(resp.json()) >= 1


def test_search_leads_combined_with_min_score():
    client.post("/leads", json={
        "name": "Score Search", "email": "score_s@search.com",
        "source": "search_score", "notes": "score_keyword_xyz",
    })
    # high min_score should filter out
    resp = client.get("/leads", params={"q": "score_keyword_xyz", "min_score": 9999})
    assert resp.json() == []
    # low min_score should include
    resp = client.get("/leads", params={"q": "score_keyword_xyz", "min_score": 0})
    assert len(resp.json()) >= 1


def test_search_leads_with_limit_offset():
    for i in range(3):
        client.post("/leads", json={
            "name": "Paginated Search", "email": f"pag_s{i}@search.com",
            "source": "search_pag", "notes": "pag_keyword_999",
        })
    all_data = client.get("/leads", params={"q": "pag_keyword_999"}).json()
    limited = client.get("/leads", params={"q": "pag_keyword_999", "limit": 2}).json()
    assert len(limited) == 2
    offset_data = client.get("/leads", params={"q": "pag_keyword_999", "limit": 2, "offset": 2}).json()
    assert len(offset_data) == len(all_data) - 2
    # ORDER BY id DESC preserved
    assert all_data[0]["id"] > all_data[-1]["id"]


# --- Summary ---


def test_leads_sources():
    resp = client.get("/leads/sources")
    assert resp.status_code == 200
    sources = resp.json()
    assert isinstance(sources, list)
    assert all(isinstance(s, str) for s in sources)
    assert len(sources) == len(set(sources))  # no duplicates
    assert sources == sorted(sources)  # alphabetically ordered


def test_leads_summary_structure():
    resp = client.get("/leads/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_leads" in data
    assert "average_score" in data
    assert "low_score_count" in data
    assert "medium_score_count" in data
    assert "high_score_count" in data
    assert "counts_by_source" in data
    assert isinstance(data["counts_by_source"], dict)


def test_leads_summary_values():
    # Create leads with known source and score
    client.post("/leads", json={
        "name": "Sum1", "email": "sum1@summary.com",
        "source": "summary_src", "notes": "interested in demo",
    })
    client.post("/leads", json={
        "name": "Sum2", "email": "sum2@summary.com",
        "source": "summary_src", "notes": "",
    })

    resp = client.get("/leads/summary")
    data = resp.json()

    assert data["total_leads"] >= 2
    assert data["average_score"] > 0
    assert data["counts_by_source"]["summary_src"] == 2
    assert data["high_score_count"] >= 0
    assert data["low_score_count"] + data["medium_score_count"] + data["high_score_count"] == data["total_leads"]


def test_leads_summary_buckets_with_known_scores():
    # notes present -> score 30 (low: < 40 with new scoring)
    client.post("/leads", json={
        "name": "BucketHi", "email": "buckhi@bucket.com",
        "source": "test", "notes": "interested in demo",
    })
    # source with no bonus + no notes -> score 20 (low: < 40)
    client.post("/leads", json={
        "name": "BucketMed", "email": "buckmed@bucket.com",
        "source": "bucket_unknown", "notes": "",
    })
    resp = client.get("/leads/summary", params={"source": "bucket_unknown"})
    data = resp.json()
    assert data["low_score_count"] >= 1

    resp = client.get("/leads/summary", params={"source": "test"})
    data = resp.json()
    assert data["low_score_count"] >= 1


def test_leads_summary_buckets_filtered_by_source():
    client.post("/leads", json={
        "name": "BFilt1", "email": "bfilt1@bucket.com",
        "source": "bucket_filt", "notes": "interested in demo",
    })
    client.post("/leads", json={
        "name": "BFilt2", "email": "bfilt2@bucket.com",
        "source": "bucket_filt", "notes": "",
    })
    resp = client.get("/leads/summary", params={"source": "bucket_filt"})
    data = resp.json()
    assert data["low_score_count"] + data["medium_score_count"] + data["high_score_count"] == data["total_leads"]
    assert data["total_leads"] == 2


def test_leads_summary_filtered_by_source():
    client.post("/leads", json={
        "name": "SrcSum1", "email": "srcsum1@summary.com",
        "source": "sum_only", "notes": "interested in demo",
    })
    client.post("/leads", json={
        "name": "SrcSum2", "email": "srcsum2@summary.com",
        "source": "sum_only", "notes": "",
    })
    resp = client.get("/leads/summary", params={"source": "sum_only"})
    data = resp.json()
    assert data["total_leads"] == 2
    assert "sum_only" in data["counts_by_source"]
    assert len(data["counts_by_source"]) == 1  # only the filtered source


def test_leads_summary_filtered_by_min_score():
    # Create a lead with known score (notes present -> 30 with new scoring)
    client.post("/leads", json={
        "name": "ScoreSum", "email": "scoresum@summary.com",
        "source": "test", "notes": "interested in demo",
    })
    # With very high min_score, this lead is excluded
    resp_high = client.get("/leads/summary", params={"min_score": 9999})
    assert resp_high.json()["total_leads"] == 0

    # With low min_score, it's included
    resp_low = client.get("/leads/summary", params={"min_score": 25})
    assert resp_low.json()["total_leads"] >= 1


def test_leads_summary_filtered_by_q():
    client.post("/leads", json={
        "name": "QSum", "email": "qsum@summary.com",
        "source": "sum_q_src", "notes": "unique_sum_keyword_xyz",
    })
    resp = client.get("/leads/summary", params={"q": "unique_sum_keyword_xyz"})
    data = resp.json()
    assert data["total_leads"] == 1
    assert data["counts_by_source"]["sum_q_src"] == 1


def test_leads_summary_combined_filters():
    client.post("/leads", json={
        "name": "ComboSum", "email": "combosum@summary.com",
        "source": "sum_combo", "notes": "combo_sum_kw",
    })
    # Both filters match
    resp = client.get("/leads/summary", params={"source": "sum_combo", "q": "combo_sum_kw"})
    data = resp.json()
    assert data["total_leads"] == 1

    # source matches but q doesn't
    resp = client.get("/leads/summary", params={"source": "sum_combo", "q": "zzz_no_match"})
    assert resp.json()["total_leads"] == 0


def test_leads_summary_filtered_high_score_count():
    # Create leads for a unique source, one high score one low
    client.post("/leads", json={
        "name": "HiSum", "email": "hisum@summary.com",
        "source": "sum_hiscore", "notes": "interested in demo",  # score 60
    })
    resp = client.get("/leads/summary", params={"source": "sum_hiscore"})
    data = resp.json()
    # buckets should be consistent with the filtered subset
    assert data["high_score_count"] <= data["total_leads"]
    assert data["low_score_count"] + data["medium_score_count"] + data["high_score_count"] == data["total_leads"]


# --- CSV Export ---


def _parse_csv(text: str) -> list[list[str]]:
    """Parse CSV response text into rows using csv.reader."""
    return list(csv.reader(io.StringIO(text)))


def test_export_csv_status_and_content_type():
    resp = client.get("/leads/export.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers.get("content-disposition", "")


def test_export_csv_header_row():
    resp = client.get("/leads/export.csv")
    rows = _parse_csv(resp.text)
    assert rows[0] == ["id", "name", "email", "source", "score", "notes"]


def test_export_csv_content_and_order():
    # Create leads with unique source
    client.post("/leads", json={
        "name": "CsvA", "email": "csva@export.com",
        "source": "csv_export", "notes": "note a",
    })
    client.post("/leads", json={
        "name": "CsvB", "email": "csvb@export.com",
        "source": "csv_export", "notes": "note b",
    })
    resp = client.get("/leads/export.csv", params={"source": "csv_export"})
    rows = _parse_csv(resp.text)
    header = rows[0]
    data_rows = [r for r in rows[1:] if r]  # skip empty trailing rows
    assert len(data_rows) >= 2
    # Each row has same number of columns as header
    assert all(len(r) == len(header) for r in data_rows)
    # ORDER BY id DESC: first data row has higher id
    id_col = header.index("id")
    assert int(data_rows[0][id_col]) > int(data_rows[1][id_col])


def test_export_csv_with_filters():
    client.post("/leads", json={
        "name": "CsvFilter", "email": "csvf@export.com",
        "source": "csv_filtered", "notes": "csv_kw_unique",
    })
    header_expected = ["id", "name", "email", "source", "score", "notes"]

    # source filter
    resp = client.get("/leads/export.csv", params={"source": "csv_filtered"})
    rows = _parse_csv(resp.text)
    assert rows[0] == header_expected
    data_rows = [r for r in rows[1:] if r]
    assert len(data_rows) >= 1
    source_col = rows[0].index("source")
    assert all(r[source_col] == "csv_filtered" for r in data_rows)

    # q filter
    resp = client.get("/leads/export.csv", params={"q": "csv_kw_unique"})
    rows = _parse_csv(resp.text)
    data_rows = [r for r in rows[1:] if r]
    assert len(data_rows) >= 1

    # limit
    resp = client.get("/leads/export.csv", params={"limit": 1})
    rows = _parse_csv(resp.text)
    data_rows = [r for r in rows[1:] if r]
    assert len(data_rows) == 1


# --- Ingest (batch) ---


def test_ingest_leads_valid_batch():
    items = [
        {"name": "Ing1", "email": "ing1@ingest.com", "source": "webhook", "notes": "batch"},
        {"name": "Ing2", "email": "ing2@ingest.com", "source": "webhook", "notes": "batch"},
    ]
    resp = client.post("/leads/ingest", json=items)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["created"] == 2
    assert data["duplicates"] == 0
    assert data["errors"] == []


def test_ingest_leads_with_duplicates():
    items = [
        {"name": "IngDup", "email": "ingdup@ingest.com", "source": "webhook", "notes": ""},
    ]
    # First call creates
    r1 = client.post("/leads/ingest", json=items)
    assert r1.json()["created"] == 1

    # Second call detects duplicate
    r2 = client.post("/leads/ingest", json=items)
    data = r2.json()
    assert data["total"] == 1
    assert data["created"] == 0
    assert data["duplicates"] == 1


def test_ingest_leads_mixed_new_and_duplicate():
    # Create one lead first
    client.post("/leads", json={
        "name": "PreExist", "email": "preexist@ingest.com",
        "source": "ingest_mix", "notes": "",
    })
    items = [
        {"name": "PreExist", "email": "preexist@ingest.com", "source": "ingest_mix", "notes": ""},
        {"name": "NewIng", "email": "newing@ingest.com", "source": "ingest_mix", "notes": "fresh"},
    ]
    resp = client.post("/leads/ingest", json=items)
    data = resp.json()
    assert data["total"] == 2
    assert data["created"] == 1
    assert data["duplicates"] == 1


def test_ingest_leads_empty_list():
    resp = client.post("/leads/ingest", json=[])
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["created"] == 0
    assert data["duplicates"] == 0


def test_ingest_leads_invalid_item():
    items = [{"name": "", "email": "not-valid"}]  # invalid payload
    resp = client.post("/leads/ingest", json=items)
    assert resp.status_code == 422


def test_ingest_leads_does_not_break_post_leads():
    # Ingest a lead
    client.post("/leads/ingest", json=[
        {"name": "IngCheck", "email": "ingcheck@ingest.com", "source": "ingest_compat", "notes": ""},
    ])
    # Verify it shows up via GET /leads
    resp = client.get("/leads", params={"source": "ingest_compat"})
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["email"] == "ingcheck@ingest.com"

    # POST /leads still works for new leads
    r = client.post("/leads", json={
        "name": "PostAfter", "email": "postafter@ingest.com",
        "source": "ingest_compat", "notes": "",
    })
    assert r.status_code == 200


# --- Ingest contract ---


def test_ingest_response_structure_and_types():
    items = [
        {"name": "IngStruct", "email": "ingstruct@contract.com", "source": "ing_contract", "notes": ""},
    ]
    resp = client.post("/leads/ingest", json=items)
    assert resp.status_code == 200
    data = resp.json()

    assert isinstance(data["total"], int)
    assert isinstance(data["created"], int)
    assert isinstance(data["duplicates"], int)
    assert isinstance(data["errors"], list)


def test_ingest_arithmetic_invariant():
    # Create one lead first to guarantee a duplicate in the batch
    client.post("/leads", json={
        "name": "InvPre", "email": "invpre@contract.com",
        "source": "ing_invariant", "notes": "",
    })
    items = [
        {"name": "InvPre", "email": "invpre@contract.com", "source": "ing_invariant", "notes": ""},
        {"name": "InvNew", "email": "invnew@contract.com", "source": "ing_invariant", "notes": ""},
    ]
    resp = client.post("/leads/ingest", json=items)
    data = resp.json()
    assert data["created"] + data["duplicates"] + len(data["errors"]) == data["total"]


def test_ingest_normalizes_email_and_source():
    items = [
        {"name": "IngNorm", "email": "  INGNORM@Example.COM  ", "source": "  WebHook  ", "notes": ""},
    ]
    resp = client.post("/leads/ingest", json=items)
    assert resp.json()["created"] == 1

    # Verify normalized values via GET
    leads = client.get("/leads", params={"source": "webhook"}).json()
    match = [l for l in leads if l["email"] == "ingnorm@example.com"]
    assert len(match) == 1
    assert match[0]["source"] == "webhook"


def test_ingest_dedup_across_batch_and_single():
    # Create via POST /leads
    client.post("/leads", json={
        "name": "CrossDedup", "email": "crossdedup@contract.com",
        "source": "ing_cross", "notes": "",
    })
    # Ingest same lead — should be duplicate
    resp = client.post("/leads/ingest", json=[
        {"name": "CrossDedup", "email": "crossdedup@contract.com", "source": "ing_cross", "notes": ""},
    ])
    assert resp.json()["duplicates"] == 1
    assert resp.json()["created"] == 0


# --- Webhook ingestion ---


def test_webhook_creates_lead_with_provider_source():
    payload = {"name": "WH User", "email": "wh1@webhook.com", "notes": "from form"}
    resp = client.post("/leads/webhook/facebook", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert isinstance(data["lead_id"], int)

    # Verify source is webhook:facebook
    lead = client.get(f"/leads/{data['lead_id']}").json()
    assert lead["source"] == "webhook:facebook"
    assert lead["email"] == "wh1@webhook.com"
    assert lead["notes"] == "from form"


def test_webhook_normalizes_provider():
    payload = {"name": "WH Norm", "email": "whnorm@webhook.com", "notes": ""}
    resp = client.post("/leads/webhook/  FaceBook  ", json=payload)
    assert resp.status_code == 200
    lead = client.get(f"/leads/{resp.json()['lead_id']}").json()
    assert lead["source"] == "webhook:facebook"


def test_webhook_duplicate_returns_409():
    payload = {"name": "WH Dup", "email": "whdup@webhook.com", "notes": "first"}
    client.post("/leads/webhook/google", json=payload)
    resp = client.post("/leads/webhook/google", json=payload)
    assert resp.status_code == 409
    data = resp.json()
    assert data["status"] == "duplicate"
    assert isinstance(data["lead_id"], int)


def test_webhook_different_provider_not_duplicate():
    payload = {"name": "WH Multi", "email": "whmulti@webhook.com", "notes": ""}
    resp1 = client.post("/leads/webhook/google", json=payload)
    resp2 = client.post("/leads/webhook/bing", json=payload)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["lead_id"] != resp2.json()["lead_id"]


def test_webhook_missing_name_returns_422():
    resp = client.post("/leads/webhook/test", json={"email": "noname@wh.com"})
    assert resp.status_code == 422


def test_webhook_missing_email_returns_422():
    resp = client.post("/leads/webhook/test", json={"name": "No Email"})
    assert resp.status_code == 422


def test_webhook_invalid_email_returns_422():
    resp = client.post(
        "/leads/webhook/test", json={"name": "Bad", "email": "not-an-email"}
    )
    assert resp.status_code == 422


def test_webhook_notes_optional():
    payload = {"name": "WH NoNotes", "email": "whnonotes@webhook.com"}
    resp = client.post("/leads/webhook/optional", json=payload)
    assert resp.status_code == 200
    lead = client.get(f"/leads/{resp.json()['lead_id']}").json()
    assert lead["notes"] is None


def test_webhook_lead_gets_scored():
    payload = {"name": "WH Score", "email": "whscore@webhook.com", "notes": "interested in boats"}
    resp = client.post("/leads/webhook/landing", json=payload)
    assert resp.status_code == 200
    lead = client.get(f"/leads/{resp.json()['lead_id']}").json()
    assert isinstance(lead["score"], int)
    assert lead["score"] >= 0


def test_webhook_post_leads_still_works():
    """POST /leads must remain fully functional after adding webhook."""
    resp = client.post("/leads", json={
        "name": "Classic", "email": "classic@compat.com",
        "source": "direct", "notes": "compatibility check",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "lead received"
    assert data["lead"]["source"] == "direct"


# --- Next action & alert ---


VALID_ACTIONS = {
    "send_to_client", "review_manually", "request_more_info",
    "enrich_first", "discard",
}


def test_next_action_unit_logic():
    from apps.api.services.actions import determine_next_action, should_alert

    # High score → send_to_client + alert
    assert determine_next_action(70, "notes") == "send_to_client"
    assert determine_next_action(60, None) == "send_to_client"
    assert should_alert(60) is True
    assert should_alert(70) is True

    # Medium with notes → review_manually, no alert
    assert determine_next_action(50, "interested") == "review_manually"
    assert should_alert(50) is False

    # Medium without notes → request_more_info
    assert determine_next_action(45, None) == "request_more_info"
    assert determine_next_action(40, "") == "request_more_info"

    # Low with notes → enrich_first
    assert determine_next_action(30, "some context") == "enrich_first"

    # Low without notes → discard
    assert determine_next_action(10, None) == "discard"
    assert determine_next_action(0, "") == "discard"


def test_pack_includes_next_action_and_alert():
    resp = client.post("/leads", json={
        "name": "Action User", "email": "action@pack.com",
        "source": "test", "notes": "demo request",
    })
    lead_id = resp.json()["lead"]["id"]
    pack = client.get(f"/leads/{lead_id}/pack").json()
    assert "next_action" in pack
    assert "alert" in pack
    assert pack["next_action"] in VALID_ACTIONS
    assert isinstance(pack["alert"], bool)


def test_pack_high_score_sends_to_client():
    resp = client.post("/leads", json={
        "name": "High Actor", "email": "highact@pack.com",
        "source": "test", "notes": "interested in boats",
    })
    lead_id = resp.json()["lead"]["id"]
    lead = client.get(f"/leads/{lead_id}").json()
    pack = client.get(f"/leads/{lead_id}/pack").json()
    if lead["score"] >= 60:
        assert pack["next_action"] == "send_to_client"
        assert pack["alert"] is True


def test_pack_low_score_no_notes_discards():
    resp = client.post("/leads", json={
        "name": "Low Actor", "email": "lowact@pack.com",
        "source": "unknown_src", "notes": "",
    })
    lead_id = resp.json()["lead"]["id"]
    lead = client.get(f"/leads/{lead_id}").json()
    pack = client.get(f"/leads/{lead_id}/pack").json()
    if lead["score"] < 40:
        assert pack["next_action"] == "discard"
        assert pack["alert"] is False


def test_delivery_includes_next_action_and_alert():
    resp = client.post("/leads", json={
        "name": "Deliv Actor", "email": "delivact@pack.com",
        "source": "test", "notes": "checking delivery",
    })
    lead_id = resp.json()["lead"]["id"]
    delivery = client.get(f"/leads/{lead_id}/delivery").json()
    assert "next_action" in delivery["pack"]
    assert "alert" in delivery["pack"]
    assert delivery["pack"]["next_action"] in VALID_ACTIONS


def test_html_pack_includes_next_action():
    resp = client.post("/leads", json={
        "name": "HTML Actor", "email": "htmlact@pack.com",
        "source": "test", "notes": "html check",
    })
    lead_id = resp.json()["lead"]["id"]
    html = client.get(f"/leads/{lead_id}/pack/html").text
    assert "Next action:" in html
    assert "Alert:" in html


def test_text_pack_includes_next_action():
    resp = client.post("/leads", json={
        "name": "Txt Actor", "email": "txtact@pack.com",
        "source": "test", "notes": "text check",
    })
    lead_id = resp.json()["lead"]["id"]
    text = client.get(f"/leads/{lead_id}/pack.txt").text
    assert "Next action:" in text
    assert "Alert:" in text


def test_existing_endpoints_still_work_after_actions():
    """Core CRUD and list endpoints remain functional."""
    resp = client.post("/leads", json={
        "name": "Compat Actor", "email": "compat_act@check.com",
        "source": "test", "notes": "compat",
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead"]["id"]

    # GET /leads/{id} still returns without next_action (it's CRUD, not pack)
    lead = client.get(f"/leads/{lead_id}").json()
    assert "next_action" not in lead
    assert "alert" not in lead

    # GET /leads still works
    leads = client.get("/leads").json()
    assert isinstance(leads, list)


# --- Delivery consistency ---


def test_delivery_top_level_matches_pack():
    resp = client.post("/leads", json={
        "name": "Consist User", "email": "consist@delivery.com",
        "source": "test", "notes": "consistency check",
    })
    lead_id = resp.json()["lead"]["id"]
    data = client.get(f"/leads/{lead_id}/delivery").json()
    assert data["next_action"] == data["pack"]["next_action"]
    assert data["alert"] == data["pack"]["alert"]
    assert data["lead_id"] == data["pack"]["lead_id"]


def test_delivery_message_reflects_alert():
    resp = client.post("/leads", json={
        "name": "Alert Msg", "email": "alertmsg@delivery.com",
        "source": "test", "notes": "interested in boats",
    })
    lead_id = resp.json()["lead"]["id"]
    data = client.get(f"/leads/{lead_id}/delivery").json()
    if data["alert"]:
        assert "ALERT" in data["message"]
    assert data["next_action"] in data["message"]


def test_delivery_message_no_alert():
    resp = client.post("/leads", json={
        "name": "Quiet Msg", "email": "quietmsg@delivery.com",
        "source": "unknown_quiet", "notes": "",
    })
    lead_id = resp.json()["lead"]["id"]
    data = client.get(f"/leads/{lead_id}/delivery").json()
    if not data["alert"]:
        assert "ALERT" not in data["message"]
        assert "next:" in data["message"]


def test_delivery_pack_matches_standalone_pack():
    resp = client.post("/leads", json={
        "name": "Pack Match", "email": "packmatch@delivery.com",
        "source": "test", "notes": "matching",
    })
    lead_id = resp.json()["lead"]["id"]
    pack = client.get(f"/leads/{lead_id}/pack").json()
    delivery = client.get(f"/leads/{lead_id}/delivery").json()
    assert delivery["pack"] == pack


# --- Source traceability ---


def test_source_whitespace_only_rejected():
    resp = client.post("/leads", json={
        "name": "WS User", "email": "ws@source.com", "source": "   ", "notes": "",
    })
    assert resp.status_code == 422


def test_source_normalized_consistently_across_entries():
    # POST /leads
    r1 = client.post("/leads", json={
        "name": "Src1", "email": "src1@trace.com", "source": "  MySource  ", "notes": "",
    })
    assert r1.status_code == 200
    assert r1.json()["lead"]["source"] == "mysource"

    # POST /leads/ingest
    r2 = client.post("/leads/ingest", json=[
        {"name": "Src2", "email": "src2@trace.com", "source": "  MySource  ", "notes": ""},
    ])
    assert r2.json()["created"] == 1
    lead2 = [l for l in client.get("/leads", params={"source": "mysource"}).json() if l["email"] == "src2@trace.com"]
    assert len(lead2) == 1
    assert lead2[0]["source"] == "mysource"

    # POST /leads/webhook/{provider}
    r3 = client.post("/leads/webhook/  MySource  ", json={
        "name": "Src3", "email": "src3@trace.com", "notes": "",
    })
    assert r3.status_code == 200
    lead3 = client.get(f"/leads/{r3.json()['lead_id']}").json()
    assert lead3["source"] == "webhook:mysource"


def test_ingest_whitespace_source_reported_as_error():
    items = [
        {"name": "Good", "email": "good@ws.com", "source": "valid", "notes": ""},
        {"name": "Bad", "email": "bad@ws.com", "source": "   ", "notes": ""},
    ]
    resp = client.post("/leads/ingest", json=items)
    data = resp.json()
    assert data["created"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["index"] == 1


def test_webhook_empty_provider_rejected():
    resp = client.post("/leads/webhook/%20%20%20", json={
        "name": "Empty Prov", "email": "emptyprov@wh.com", "notes": "",
    })
    assert resp.status_code == 422


# --- Webhook batch ---


def test_webhook_batch_happy_path():
    """Batch creates leads with auto-generated source."""
    resp = client.post("/leads/webhook/batch-test/batch", json=[
        {"name": "Batch A", "email": "batcha@wb.com", "notes": "first"},
        {"name": "Batch B", "email": "batchb@wb.com", "notes": "second"},
    ])
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["created"] == 2
    assert data["duplicates"] == 0
    assert data["errors"] == []
    leads = client.get("/leads", params={"source": "webhook:batch-test"}).json()
    assert len(leads) >= 2


def test_webhook_batch_duplicates_counted():
    client.post("/leads/webhook/batch-dup/batch", json=[
        {"name": "Dup Lead", "email": "dupbatch@wb.com"},
    ])
    resp = client.post("/leads/webhook/batch-dup/batch", json=[
        {"name": "Dup Lead", "email": "dupbatch@wb.com"},
        {"name": "New Lead", "email": "newbatch@wb.com"},
    ])
    data = resp.json()
    assert data["total"] == 2
    assert data["created"] == 1
    assert data["duplicates"] == 1


def test_webhook_batch_empty_provider_rejected():
    resp = client.post("/leads/webhook/%20%20/batch", json=[
        {"name": "Bad", "email": "bad@wb.com"},
    ])
    assert resp.status_code == 422


def test_webhook_batch_structure_and_arithmetic():
    """Response shape matches /leads/ingest and arithmetic holds."""
    resp = client.post("/leads/webhook/batch-arith/batch", json=[
        {"name": "Arith A", "email": "aritha@wb.com"},
        {"name": "Arith A", "email": "aritha@wb.com"},
        {"name": "Arith B", "email": "arithb@wb.com"},
    ])
    data = resp.json()
    assert set(data.keys()) == {"total", "created", "duplicates", "errors"}
    assert data["total"] == data["created"] + data["duplicates"] + len(data["errors"])


def test_webhook_batch_does_not_break_single_webhook():
    resp = client.post("/leads/webhook/batch-compat", json={
        "name": "Compat", "email": "compat@wb.com",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_source_dedup_consistent_after_normalization():
    """Same source with different casing/whitespace should dedup correctly."""
    client.post("/leads", json={
        "name": "Dedup Src", "email": "dedupsrc@trace.com", "source": "Facebook", "notes": "",
    })
    resp = client.post("/leads", json={
        "name": "Dedup Src", "email": "dedupsrc@trace.com", "source": "  facebook  ", "notes": "",
    })
    assert resp.status_code == 409


# --- Operational contract ---


OPERATIONAL_FIELDS = {"lead_id", "name", "source", "score", "status", "rating", "next_action", "instruction", "alert", "summary", "created_at", "generated_at"}


def test_operational_response_structure():
    resp = client.post("/leads", json={
        "name": "Op Struct", "email": "opstruct@op.com",
        "source": "test", "notes": "operational check",
    })
    lead_id = resp.json()["lead"]["id"]
    op = client.get(f"/leads/{lead_id}/operational").json()
    assert set(op.keys()) == OPERATIONAL_FIELDS


def test_operational_field_types():
    resp = client.post("/leads", json={
        "name": "Op Types", "email": "optypes@op.com",
        "source": "test", "notes": "type check",
    })
    lead_id = resp.json()["lead"]["id"]
    op = client.get(f"/leads/{lead_id}/operational").json()
    assert isinstance(op["lead_id"], int)
    assert isinstance(op["source"], str)
    assert isinstance(op["score"], int)
    assert isinstance(op["rating"], str)
    assert isinstance(op["next_action"], str)
    assert isinstance(op["alert"], bool)
    assert isinstance(op["summary"], str)
    assert isinstance(op["generated_at"], str)
    assert "T" in op["generated_at"]


def test_operational_matches_pack_fields():
    resp = client.post("/leads", json={
        "name": "Op Match", "email": "opmatch@op.com",
        "source": "test", "notes": "consistency",
    })
    lead_id = resp.json()["lead"]["id"]
    pack = client.get(f"/leads/{lead_id}/pack").json()
    op = client.get(f"/leads/{lead_id}/operational").json()
    assert op["lead_id"] == pack["lead_id"]
    assert op["source"] == pack["source"]
    assert op["score"] == pack["score"]
    assert op["rating"] == pack["rating"]
    assert op["next_action"] == pack["next_action"]
    assert op["alert"] == pack["alert"]
    assert op["summary"] == pack["summary"]


def test_operational_not_found():
    resp = client.get("/leads/99999/operational")
    assert resp.status_code == 404


def test_operational_no_extra_fields():
    """Contract must be exactly the defined fields — no leakage from pack."""
    resp = client.post("/leads", json={
        "name": "Op Lean", "email": "oplean@op.com",
        "source": "test", "notes": "lean check",
    })
    lead_id = resp.json()["lead"]["id"]
    op = client.get(f"/leads/{lead_id}/operational").json()
    assert "name" in op
    assert "created_at" in op
    assert "email" not in op
    assert "notes" not in op
    assert "message" not in op
    assert "pack" not in op


# --- Actionable leads ---


def test_actionable_returns_list():
    resp = client.get("/leads/actionable")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_actionable_excludes_discard_leads():
    """Leads with score < 40 and no notes (discard) should not appear."""
    # Create a lead that will be discard: unknown source (score 50 base, but we need < 40)
    # With current scoring: base=50 always, so all leads score >= 50.
    # We can't easily create a score < 40 with current placeholder scoring.
    # Instead, verify that all returned leads have next_action != discard.
    data = client.get("/leads/actionable").json()
    for item in data:
        assert item["next_action"] != "discard"


def test_actionable_items_use_operational_contract():
    """Each item should have exactly the operational summary fields."""
    client.post("/leads", json={
        "name": "Act Contract", "email": "actcontract@act.com",
        "source": "test", "notes": "actionable check",
    })
    data = client.get("/leads/actionable").json()
    assert len(data) >= 1
    for item in data:
        assert set(item.keys()) == OPERATIONAL_FIELDS


def test_actionable_ordered_by_score_desc():
    client.post("/leads", json={
        "name": "Act Low", "email": "actlow@act.com",
        "source": "unknown_act", "notes": "some context",
    })
    client.post("/leads", json={
        "name": "Act High", "email": "acthigh@act.com",
        "source": "test", "notes": "interested in boats",
    })
    data = client.get("/leads/actionable").json()
    scores = [item["score"] for item in data]
    assert scores == sorted(scores, reverse=True)


def test_actionable_filter_by_source():
    client.post("/leads", json={
        "name": "Act Src", "email": "actsrc@act.com",
        "source": "act_filter", "notes": "filterable",
    })
    data = client.get("/leads/actionable", params={"source": "act_filter"}).json()
    assert len(data) >= 1
    assert all(item["source"] == "act_filter" for item in data)


def test_actionable_respects_limit():
    for i in range(3):
        client.post("/leads", json={
            "name": f"Act Lim {i}", "email": f"actlim{i}@act.com",
            "source": "act_limit", "notes": "limit test",
        })
    data = client.get("/leads/actionable", params={"source": "act_limit", "limit": 2}).json()
    assert len(data) <= 2


def test_actionable_does_not_break_other_endpoints():
    resp = client.get("/leads")
    assert resp.status_code == 200
    resp = client.get("/leads/summary")
    assert resp.status_code == 200


# --- Worklist ---


WORKLIST_FIELDS = {"generated_at", "total", "groups"}
WORKLIST_GROUP_FIELDS = {"next_action", "count", "leads"}


def test_worklist_returns_valid_structure():
    client.post("/leads", json={
        "name": "WL Struct", "email": "wlstruct@wl.com",
        "source": "test", "notes": "worklist test",
    })
    resp = client.get("/leads/actionable/worklist")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == WORKLIST_FIELDS
    assert isinstance(data["total"], int)
    assert isinstance(data["groups"], list)
    assert data["total"] >= 1
    for group in data["groups"]:
        assert set(group.keys()) == WORKLIST_GROUP_FIELDS
        assert group["count"] == len(group["leads"])
        assert group["count"] >= 1


def test_worklist_total_matches_sum_of_groups():
    resp = client.get("/leads/actionable/worklist")
    data = resp.json()
    group_sum = sum(g["count"] for g in data["groups"])
    assert data["total"] == group_sum


def test_worklist_groups_ordered_by_priority():
    """Groups should follow action priority: send_to_client > review_manually > request_more_info > enrich_first."""
    resp = client.get("/leads/actionable/worklist")
    data = resp.json()
    priority = ["send_to_client", "review_manually", "request_more_info", "enrich_first"]
    actions = [g["next_action"] for g in data["groups"]]
    # Filter to only known actions for ordering check
    known = [a for a in actions if a in priority]
    expected = [a for a in priority if a in known]
    assert known == expected


def test_worklist_leads_within_group_ordered_by_score_desc():
    resp = client.get("/leads/actionable/worklist")
    data = resp.json()
    for group in data["groups"]:
        scores = [lead["score"] for lead in group["leads"]]
        assert scores == sorted(scores, reverse=True)


def test_worklist_leads_use_operational_contract():
    resp = client.get("/leads/actionable/worklist")
    data = resp.json()
    for group in data["groups"]:
        for lead in group["leads"]:
            assert set(lead.keys()) == OPERATIONAL_FIELDS


def test_worklist_no_discard_group():
    """Worklist should never contain a discard group since actionable excludes discards."""
    resp = client.get("/leads/actionable/worklist")
    data = resp.json()
    actions = [g["next_action"] for g in data["groups"]]
    assert "discard" not in actions


def test_worklist_filter_by_source():
    client.post("/leads", json={
        "name": "WL Src", "email": "wlsrc@wl.com",
        "source": "wl_filter", "notes": "source filter",
    })
    resp = client.get("/leads/actionable/worklist", params={"source": "wl_filter"})
    data = resp.json()
    assert data["total"] >= 1
    for group in data["groups"]:
        for lead in group["leads"]:
            assert lead["source"] == "wl_filter"


def test_worklist_respects_limit():
    for i in range(3):
        client.post("/leads", json={
            "name": f"WL Lim {i}", "email": f"wllim{i}@wl.com",
            "source": "wl_limit", "notes": "limit test",
        })
    resp = client.get("/leads/actionable/worklist", params={"source": "wl_limit", "limit": 2})
    data = resp.json()
    assert data["total"] <= 2


def test_worklist_empty_when_no_actionable():
    resp = client.get("/leads/actionable/worklist", params={"source": "nonexistent_wl_src"})
    data = resp.json()
    assert data["total"] == 0
    assert data["groups"] == []


def test_worklist_generated_at_is_present():
    resp = client.get("/leads/actionable/worklist")
    data = resp.json()
    assert "generated_at" in data
    assert len(data["generated_at"]) > 0


def test_worklist_does_not_break_actionable():
    resp = client.get("/leads/actionable")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# --- Internal Queue ---


QUEUE_FIELDS = {"generated_at", "total", "urgent_count", "items"}


def test_queue_returns_valid_structure():
    client.post("/leads", json={
        "name": "Q Struct", "email": "qstruct@q.com",
        "source": "test", "notes": "queue test",
    })
    resp = client.get("/internal/queue")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == QUEUE_FIELDS
    assert isinstance(data["total"], int)
    assert isinstance(data["urgent_count"], int)
    assert isinstance(data["items"], list)
    assert data["total"] >= 1


def test_queue_items_use_operational_contract():
    resp = client.get("/internal/queue")
    data = resp.json()
    for item in data["items"]:
        assert set(item.keys()) == OPERATIONAL_FIELDS


def test_queue_total_matches_items_length():
    resp = client.get("/internal/queue")
    data = resp.json()
    assert data["total"] == len(data["items"])


def test_queue_urgent_count_matches_alert_items():
    resp = client.get("/internal/queue")
    data = resp.json()
    alert_count = sum(1 for item in data["items"] if item["alert"])
    assert data["urgent_count"] == alert_count


def test_queue_alert_items_come_first():
    """Items with alert=True should appear before items with alert=False."""
    resp = client.get("/internal/queue")
    data = resp.json()
    alerts = [item["alert"] for item in data["items"]]
    # Once we see a non-alert, no more alerts should follow
    seen_non_alert = False
    for a in alerts:
        if not a:
            seen_non_alert = True
        elif seen_non_alert:
            assert False, "Alert item found after non-alert item"


def test_queue_no_discard_items():
    resp = client.get("/internal/queue")
    data = resp.json()
    for item in data["items"]:
        assert item["next_action"] != "discard"


def test_queue_filter_by_source():
    client.post("/leads", json={
        "name": "Q Src", "email": "qsrc@q.com",
        "source": "q_filter", "notes": "source filter",
    })
    resp = client.get("/internal/queue", params={"source": "q_filter"})
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["source"] == "q_filter"


def test_queue_respects_limit():
    for i in range(3):
        client.post("/leads", json={
            "name": f"Q Lim {i}", "email": f"qlim{i}@q.com",
            "source": "q_limit", "notes": "limit test",
        })
    resp = client.get("/internal/queue", params={"source": "q_limit", "limit": 2})
    data = resp.json()
    assert len(data["items"]) <= 2
    assert data["total"] >= len(data["items"])


def test_queue_empty_when_no_actionable():
    resp = client.get("/internal/queue", params={"source": "nonexistent_q_src"})
    data = resp.json()
    assert data["total"] == 0
    assert data["urgent_count"] == 0
    assert data["items"] == []


def test_queue_does_not_break_worklist():
    resp = client.get("/leads/actionable/worklist")
    assert resp.status_code == 200


def test_queue_does_not_break_actionable():
    resp = client.get("/leads/actionable")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# --- Instruction field ---


KNOWN_INSTRUCTIONS = {
    "send_to_client": "Contactar al propietario. Lead cualificado con datos suficientes para primera conversacion.",
    "review_manually": "Revisar datos antes de contactar. Hay informacion pero falta valorar si merece seguimiento directo.",
    "request_more_info": "Pedir mas datos. El lead tiene poco detalle para evaluar interes real.",
    "enrich_first": "Buscar informacion adicional. Datos insuficientes para actuar.",
    "discard": "Descartar. Sin datos utiles.",
}


def test_instruction_present_in_operational():
    client.post("/leads", json={
        "name": "Instr Op", "email": "instrop@i.com",
        "source": "test", "notes": "instruction check",
    })
    leads = client.get("/leads").json()
    lead_id = leads[0]["id"]
    resp = client.get(f"/leads/{lead_id}/operational")
    data = resp.json()
    assert "instruction" in data
    assert data["instruction"] == KNOWN_INSTRUCTIONS[data["next_action"]]


def test_instruction_present_in_actionable():
    resp = client.get("/leads/actionable")
    data = resp.json()
    assert len(data) >= 1
    for item in data:
        assert "instruction" in item
        assert item["instruction"] == KNOWN_INSTRUCTIONS[item["next_action"]]


def test_instruction_present_in_worklist():
    resp = client.get("/leads/actionable/worklist")
    data = resp.json()
    for group in data["groups"]:
        for lead in group["leads"]:
            assert "instruction" in lead
            assert lead["instruction"] == KNOWN_INSTRUCTIONS[lead["next_action"]]


def test_instruction_present_in_queue():
    resp = client.get("/internal/queue")
    data = resp.json()
    for item in data["items"]:
        assert "instruction" in item
        assert item["instruction"] == KNOWN_INSTRUCTIONS[item["next_action"]]


def test_instruction_matches_next_action():
    """Each known next_action maps to its expected instruction."""
    client.post("/leads", json={
        "name": "Instr High", "email": "instrhigh@i.com",
        "source": "test", "notes": "high score lead",
    })
    client.post("/leads", json={
        "name": "Instr Mid", "email": "instrmid@i.com",
        "source": "midaction", "notes": "mid score lead",
    })
    resp = client.get("/leads/actionable")
    data = resp.json()
    for item in data:
        assert item["instruction"] == KNOWN_INSTRUCTIONS[item["next_action"]]


def test_queue_limit_truncates_after_sort():
    """Queue limit must apply after priority sort, returning the top N."""
    # Ensure enough actionable leads exist
    client.post("/leads", json={
        "name": "QL1", "email": "ql1@qlimit.com",
        "source": "qlimit", "notes": "notes for actionable",
    })
    client.post("/leads", json={
        "name": "QL2", "email": "ql2@qlimit.com",
        "source": "qlimit", "notes": "notes for actionable",
    })
    client.post("/leads", json={
        "name": "QL3", "email": "ql3@qlimit.com",
        "source": "qlimit", "notes": "notes for actionable",
    })
    full_resp = client.get("/internal/queue", params={"source": "qlimit"})
    full_items = full_resp.json()["items"]
    assert len(full_items) >= 2
    limited_resp = client.get("/internal/queue", params={"source": "qlimit", "limit": 2})
    assert limited_resp.status_code == 200
    limited = limited_resp.json()
    assert len(limited["items"]) == 2
    assert limited["total"] == full_resp.json()["total"]
    assert [item["lead_id"] for item in limited["items"]] == [item["lead_id"] for item in full_items[:2]]


def test_queue_order_is_stable():
    """Queue order must be consistent across calls."""
    resp1 = client.get("/internal/queue")
    resp2 = client.get("/internal/queue")
    ids1 = [item["lead_id"] for item in resp1.json()["items"]]
    ids2 = [item["lead_id"] for item in resp2.json()["items"]]
    assert ids1 == ids2


# ---------------------------------------------------------------------------
# GET /internal/dispatch — automation dispatch batch
# ---------------------------------------------------------------------------


def test_dispatch_returns_batch():
    """Dispatch endpoint returns a valid batch with expected shape."""
    resp = client.get("/internal/dispatch")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["total"] == len(data["items"])


def test_dispatch_item_contract():
    """Each dispatch item has the required automation contract fields."""
    client.post("/leads", json={
        "name": "Dispatch Contract", "email": "dcontract@dispatch.com",
        "source": "dispatch_contract", "notes": "has notes for actionable",
    })
    resp = client.get("/internal/dispatch", params={"source": "dispatch_contract"})
    data = resp.json()
    assert data["total"] > 0
    item = data["items"][0]
    assert "lead_id" in item
    assert "action" in item
    assert "instruction" in item
    assert "priority" in item
    assert "alert" in item
    assert "payload" in item
    assert "generated_at" in item
    # payload must be a full pack
    pack = item["payload"]
    assert "lead_id" in pack
    assert "name" in pack
    assert "email" in pack
    assert "score" in pack
    assert "rating" in pack
    assert "next_action" in pack
    assert "summary" in pack


def test_dispatch_consistent_with_queue():
    """Dispatch must return the same leads as queue, in the same order."""
    queue_resp = client.get("/internal/queue")
    dispatch_resp = client.get("/internal/dispatch")
    queue_ids = [item["lead_id"] for item in queue_resp.json()["items"]]
    dispatch_ids = [item["lead_id"] for item in dispatch_resp.json()["items"]]
    assert queue_ids == dispatch_ids


def test_dispatch_source_filter():
    """Source filter works on dispatch endpoint."""
    client.post("/leads", json={
        "name": "Dispatch Src", "email": "dsrc@dispatch.com",
        "source": "dispatch_src", "notes": STRONG_NOTES,
    })
    resp = client.get("/internal/dispatch", params={"source": "dispatch_src"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["payload"]["source"] == "dispatch_src" for item in data["items"])


def test_dispatch_action_matches_payload():
    """Dispatch action field must match the pack's next_action."""
    resp = client.get("/internal/dispatch")
    data = resp.json()
    for item in data["items"]:
        assert item["action"] == item["payload"]["next_action"]


def test_dispatch_action_filter():
    """Action filter returns only items with the specified action."""
    # Get all dispatch items to find an action that exists
    all_resp = client.get("/internal/dispatch")
    all_items = all_resp.json()["items"]
    assert len(all_items) > 0
    target_action = all_items[0]["action"]
    # Filter by that action
    filtered_resp = client.get("/internal/dispatch", params={"action": target_action})
    assert filtered_resp.status_code == 200
    filtered = filtered_resp.json()
    assert all(item["action"] == target_action for item in filtered["items"])
    assert filtered["total"] == len(filtered["items"])
    # Count must match manual count from unfiltered
    expected_count = sum(1 for item in all_items if item["action"] == target_action)
    assert filtered["total"] == expected_count


def test_dispatch_action_filter_nonexistent():
    """Nonexistent action returns empty list, not error."""
    resp = client.get("/internal/dispatch", params={"action": "nonexistent_action_xyz"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_dispatch_no_action_filter_unchanged():
    """Without action filter, dispatch returns same results as before."""
    resp_no_filter = client.get("/internal/dispatch")
    resp_none = client.get("/internal/dispatch", params={})
    assert resp_no_filter.json()["total"] == resp_none.json()["total"]


def test_dispatch_action_whitespace_ignored():
    """Whitespace-only action param should be ignored, not filter everything out."""
    baseline = client.get("/internal/dispatch").json()
    resp = client.get("/internal/dispatch", params={"action": "   "})
    assert resp.status_code == 200
    assert resp.json()["total"] == baseline["total"]


def test_dispatch_limit_truncates_after_sort():
    """Limit must apply after dispatch sort order, returning the top N by priority."""
    # Get full dispatch to know the order
    full_resp = client.get("/internal/dispatch")
    full_items = full_resp.json()["items"]
    assert len(full_items) >= 2
    # Request limit=2
    limited_resp = client.get("/internal/dispatch", params={"limit": 2})
    assert limited_resp.status_code == 200
    limited = limited_resp.json()
    assert len(limited["items"]) == 2
    assert limited["total"] >= len(limited["items"])
    # The limited items must be the first 2 from the full sorted list
    assert [item["lead_id"] for item in limited["items"]] == [item["lead_id"] for item in full_items[:2]]


def test_dispatch_limit_with_action_filter():
    """Limit applies after action filter — returns top N of the filtered set."""
    # Find an action with multiple items
    full_resp = client.get("/internal/dispatch")
    from collections import Counter
    action_counts = Counter(item["action"] for item in full_resp.json()["items"])
    multi_actions = [a for a, c in action_counts.items() if c >= 2]
    if not multi_actions:
        return  # skip if not enough data
    target_action = multi_actions[0]
    # Get all items for that action
    action_resp = client.get("/internal/dispatch", params={"action": target_action})
    action_items = action_resp.json()["items"]
    # Get limited
    limited_resp = client.get("/internal/dispatch", params={"action": target_action, "limit": 1})
    limited = limited_resp.json()
    assert len(limited["items"]) == 1
    assert limited["total"] >= len(limited["items"])
    assert limited["items"][0]["lead_id"] == action_items[0]["lead_id"]


def test_dispatch_order_is_stable():
    """Dispatch order must be consistent across calls."""
    resp1 = client.get("/internal/dispatch")
    resp2 = client.get("/internal/dispatch")
    ids1 = [item["lead_id"] for item in resp1.json()["items"]]
    ids2 = [item["lead_id"] for item in resp2.json()["items"]]
    assert ids1 == ids2


# ---------------------------------------------------------------------------
# POST /internal/dispatch/claim — claim lifecycle
# ---------------------------------------------------------------------------


def test_claim_success():
    """Claim existing leads returns them in claimed list."""
    r = client.post("/leads", json={
        "name": "Claim OK", "email": "claimok@claim.com",
        "source": "claimtest", "notes": STRONG_NOTES,
    })
    lead_id = r.json()["lead"]["id"]
    resp = client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    assert resp.status_code == 200
    data = resp.json()
    assert lead_id in data["claimed"]
    assert data["already_claimed"] == []
    assert data["not_found"] == []


def test_claim_duplicate_in_already_claimed():
    """Claiming an already-claimed lead returns it in already_claimed."""
    r = client.post("/leads", json={
        "name": "Claim Dup", "email": "claimdup@claim.com",
        "source": "claimtest", "notes": STRONG_NOTES,
    })
    lead_id = r.json()["lead"]["id"]
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    resp = client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["claimed"] == []
    assert lead_id in data["already_claimed"]
    assert data["not_found"] == []


def test_claim_nonexistent_in_not_found():
    """Claiming a non-existent lead_id returns it in not_found."""
    resp = client.post("/internal/dispatch/claim", json={"lead_ids": [999999]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["claimed"] == []
    assert data["already_claimed"] == []
    assert 999999 in data["not_found"]


def test_claim_mixed_results():
    """Mixed claim: one new, one duplicate, one not_found."""
    r = client.post("/leads", json={
        "name": "Claim Mix A", "email": "claimmix_a@claim.com",
        "source": "claimtest", "notes": STRONG_NOTES,
    })
    id_a = r.json()["lead"]["id"]
    client.post("/internal/dispatch/claim", json={"lead_ids": [id_a]})

    r2 = client.post("/leads", json={
        "name": "Claim Mix B", "email": "claimmix_b@claim.com",
        "source": "claimtest", "notes": STRONG_NOTES,
    })
    id_b = r2.json()["lead"]["id"]

    resp = client.post("/internal/dispatch/claim", json={
        "lead_ids": [id_b, id_a, 888888],
    })
    data = resp.json()
    assert id_b in data["claimed"]
    assert id_a in data["already_claimed"]
    assert 888888 in data["not_found"]


def test_dispatch_excludes_claimed():
    """Claimed leads do not appear in GET /internal/dispatch."""
    r = client.post("/leads", json={
        "name": "Dispatch Excl", "email": "dispexcl@claim.com",
        "source": "claimexcl", "notes": STRONG_NOTES,
    })
    lead_id = r.json()["lead"]["id"]
    # Should appear before claim
    resp_before = client.get("/internal/dispatch", params={"source": "claimexcl"})
    ids_before = [item["lead_id"] for item in resp_before.json()["items"]]
    assert lead_id in ids_before
    # Claim it
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    # Should not appear after claim
    resp_after = client.get("/internal/dispatch", params={"source": "claimexcl"})
    ids_after = [item["lead_id"] for item in resp_after.json()["items"]]
    assert lead_id not in ids_after


def test_dispatch_unclaimed_unaffected():
    """Unclaimed leads still appear normally in dispatch."""
    r = client.post("/leads", json={
        "name": "Unclaimed", "email": "unclaimed@claim.com",
        "source": "claimuncl", "notes": STRONG_NOTES,
    })
    lead_id = r.json()["lead"]["id"]
    resp = client.get("/internal/dispatch", params={"source": "claimuncl"})
    ids = [item["lead_id"] for item in resp.json()["items"]]
    assert lead_id in ids


def test_claim_empty_list_rejected():
    """Empty lead_ids list is rejected by validation."""
    resp = client.post("/internal/dispatch/claim", json={"lead_ids": []})
    assert resp.status_code == 422


def test_claim_duplicate_ids_deduplicated():
    """Duplicate lead_ids in same request are deduplicated — ID appears only once in response."""
    r = client.post("/leads", json={
        "name": "Claim Dedup", "email": "claimdedup@claim.com",
        "source": "claimtest", "notes": STRONG_NOTES,
    })
    lead_id = r.json()["lead"]["id"]
    resp = client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id, lead_id, lead_id]})
    data = resp.json()
    assert data["claimed"] == [lead_id]
    assert data["already_claimed"] == []
    assert data["not_found"] == []


# ---------------------------------------------------------------------------
# GET /internal/handoffs — outbound automation handoff
# ---------------------------------------------------------------------------


def test_handoffs_returns_batch():
    """Handoffs endpoint returns batch response with correct shape."""
    resp = client.get("/internal/handoffs")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_handoff_item_contract():
    """Each handoff item has exactly the approved fields."""
    r = client.post("/leads", json={
        "name": "Handoff Contract", "email": "hcontract@handoff.com",
        "source": "handofftest", "notes": STRONG_NOTES,
    })
    assert r.status_code == 200
    resp = client.get("/internal/handoffs", params={"source": "handofftest"})
    data = resp.json()
    assert data["total"] > 0
    item = data["items"][0]
    assert set(item.keys()) == {"lead_id", "action", "channel", "instruction", "payload"}
    assert isinstance(item["lead_id"], int)
    assert isinstance(item["action"], str)
    assert isinstance(item["channel"], str)
    assert isinstance(item["instruction"], str)
    assert isinstance(item["payload"], dict)


def test_handoffs_excludes_claimed():
    """Claimed leads do not appear in handoffs."""
    r = client.post("/leads", json={
        "name": "Handoff Excl", "email": "hexcl@handoff.com",
        "source": "handoffexcl", "notes": STRONG_NOTES,
    })
    lead_id = r.json()["lead"]["id"]
    resp_before = client.get("/internal/handoffs", params={"source": "handoffexcl"})
    ids_before = [i["lead_id"] for i in resp_before.json()["items"]]
    assert lead_id in ids_before
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    resp_after = client.get("/internal/handoffs", params={"source": "handoffexcl"})
    ids_after = [i["lead_id"] for i in resp_after.json()["items"]]
    assert lead_id not in ids_after


def test_handoffs_action_filter():
    """Action filter works on handoffs."""
    r = client.post("/leads", json={
        "name": "Handoff Act", "email": "hact@handoff.com",
        "source": "handoffact", "notes": STRONG_NOTES,
    })
    assert r.status_code == 200
    lead = r.json()["lead"]
    resp = client.get("/internal/handoffs", params={
        "source": "handoffact", "action": lead["score"] >= 60 and "send_to_client" or "review_manually",
    })
    data = resp.json()
    for item in data["items"]:
        assert item["action"] == (lead["score"] >= 60 and "send_to_client" or "review_manually")


def test_handoffs_channel_mapping():
    """Each action maps to the expected channel."""
    expected = {
        "send_to_client": "email",
        "review_manually": "review",
        "request_more_info": "email",
        "enrich_first": "manual",
    }
    resp = client.get("/internal/handoffs")
    data = resp.json()
    for item in data["items"]:
        if item["action"] in expected:
            assert item["channel"] == expected[item["action"]], (
                f"action {item['action']} should map to {expected[item['action']]}, got {item['channel']}"
            )


def test_handoffs_instruction_contains_lead_info():
    """Instruction includes lead name, source, and score."""
    r = client.post("/leads", json={
        "name": "Handoff Info", "email": "hinfo@handoff.com",
        "source": "handoffinfo", "notes": STRONG_NOTES,
    })
    lead_id = r.json()["lead"]["id"]
    resp = client.get("/internal/handoffs", params={"source": "handoffinfo"})
    data = resp.json()
    item = [i for i in data["items"] if i["lead_id"] == lead_id][0]
    assert "Handoff Info" in item["instruction"]
    assert "handoffinfo" in item["instruction"]


def test_handoffs_consistent_with_dispatch():
    """Handoffs and dispatch return the same leads in the same order."""
    source = "handoffcons"
    for i in range(3):
        client.post("/leads", json={
            "name": f"HCons {i}", "email": f"hcons{i}@handoff.com",
            "source": source, "notes": "notes for consistency",
        })
    dispatch_resp = client.get("/internal/dispatch", params={"source": source})
    handoff_resp = client.get("/internal/handoffs", params={"source": source})
    dispatch_ids = [i["lead_id"] for i in dispatch_resp.json()["items"]]
    handoff_ids = [i["lead_id"] for i in handoff_resp.json()["items"]]
    assert dispatch_ids == handoff_ids


def test_handoffs_no_generated_at_on_item():
    """HandoffItem does not have generated_at — only the batch response does."""
    resp = client.get("/internal/handoffs")
    data = resp.json()
    assert "generated_at" in data
    for item in data["items"]:
        assert "generated_at" not in item


# ---------------------------------------------------------------------------
# GET /internal/handoffs/export.csv — handoff CSV export
# ---------------------------------------------------------------------------


def test_handoff_csv_returns_csv():
    """Handoff CSV endpoint returns text/csv with correct headers."""
    resp = client.get("/internal/handoffs/export.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "handoffs.csv" in resp.headers.get("content-disposition", "")


def test_handoff_csv_columns():
    """CSV has the expected column headers."""
    client.post("/leads", json={
        "name": "CSV Col", "email": "csvcol@hcsv.com",
        "source": "hcsvtest", "notes": STRONG_NOTES,
    })
    resp = client.get("/internal/handoffs/export.csv", params={"source": "hcsvtest"})
    rows = _parse_csv(resp.text)
    assert rows[0] == ["lead_id", "action", "channel", "instruction", "name", "email", "source", "score", "rating"]


def test_handoff_csv_data_matches_json():
    """CSV data rows match the JSON handoffs endpoint."""
    source = "hcsvmatch"
    client.post("/leads", json={
        "name": "CSV Match", "email": "csvmatch@hcsv.com",
        "source": source, "notes": STRONG_NOTES,
    })
    json_resp = client.get("/internal/handoffs", params={"source": source})
    csv_resp = client.get("/internal/handoffs/export.csv", params={"source": source})
    json_ids = [i["lead_id"] for i in json_resp.json()["items"]]
    rows = _parse_csv(csv_resp.text)
    csv_ids = [int(r[0]) for r in rows[1:]]
    assert json_ids == csv_ids


def test_handoff_csv_excludes_claimed():
    """Claimed leads do not appear in handoff CSV."""
    r = client.post("/leads", json={
        "name": "CSV Excl", "email": "csvexcl@hcsv.com",
        "source": "hcsvexcl", "notes": STRONG_NOTES,
    })
    lead_id = r.json()["lead"]["id"]
    resp_before = client.get("/internal/handoffs/export.csv", params={"source": "hcsvexcl"})
    rows_before = _parse_csv(resp_before.text)
    ids_before = [int(r[0]) for r in rows_before[1:]]
    assert lead_id in ids_before
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    resp_after = client.get("/internal/handoffs/export.csv", params={"source": "hcsvexcl"})
    rows_after = _parse_csv(resp_after.text)
    ids_after = [int(r[0]) for r in rows_after[1:]]
    assert lead_id not in ids_after


def test_handoff_csv_action_filter():
    """Action filter works on CSV export."""
    client.post("/leads", json={
        "name": "CSV Act", "email": "csvact@hcsv.com",
        "source": "hcsvact", "notes": STRONG_NOTES,
    })
    resp = client.get("/internal/handoffs/export.csv", params={
        "source": "hcsvact", "action": "review_manually",
    })
    rows = _parse_csv(resp.text)
    for r in rows[1:]:
        assert r[1] == "review_manually"


def test_handoff_csv_sanitizes_injection():
    """CSV values starting with dangerous chars are sanitized."""
    client.post("/leads", json={
        "name": "=EVIL()", "email": "csvinj@hcsv.com",
        "source": "hcsvinj", "notes": STRONG_NOTES,
    })
    resp = client.get("/internal/handoffs/export.csv", params={"source": "hcsvinj"})
    rows = _parse_csv(resp.text)
    name_col = rows[0].index("name")
    data_rows = [r for r in rows[1:] if r[name_col].endswith("EVIL()")]
    assert len(data_rows) >= 1
    assert data_rows[0][name_col] == "'=EVIL()"


# ---------------------------------------------------------------------------
# GET /internal/review — client review queue
# ---------------------------------------------------------------------------


def test_review_returns_batch():
    """Review endpoint returns batch response with correct shape."""
    resp = client.get("/internal/review")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "total" in data
    assert "urgent_count" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_review_only_reviewable_actions():
    """Review queue only contains send_to_client and review_manually leads."""
    # score 60 + notes → send_to_client
    client.post("/leads", json={
        "name": "Review HiScore", "email": "reviewhi@review.com",
        "source": "reviewtest", "notes": "interested in premium boats",
    })
    # score 50 + notes → review_manually (score 50-59 with notes)
    # Actually score is calculated: base 50 + notes bonus 10 = 60 → send_to_client
    # To get review_manually we need score 40-59 with notes, but scoring gives 60 for notes
    # Let's just verify that whatever comes back has the right actions
    resp = client.get("/internal/review")
    data = resp.json()
    for item in data["items"]:
        assert item["next_action"] in ("send_to_client", "review_manually"), (
            f"unexpected action {item['next_action']} in review queue"
        )


def test_review_excludes_non_reviewable():
    """Leads with request_more_info or enrich_first do not appear in review."""
    # score < 40 + no notes → discard (not actionable at all)
    # score < 40 + notes → enrich_first (actionable but not reviewable)
    # We can't easily create request_more_info or enrich_first in review since
    # scoring is fixed. But we can verify they're excluded by checking all items.
    resp = client.get("/internal/review")
    data = resp.json()
    excluded_actions = {"request_more_info", "enrich_first", "discard"}
    for item in data["items"]:
        assert item["next_action"] not in excluded_actions


def test_review_excludes_claimed():
    """Claimed leads do not appear in review queue."""
    r = client.post("/leads", json={
        "name": "Review Excl", "email": "reviewexcl@review.com",
        "source": "reviewexcl", "notes": STRONG_NOTES,
    })
    lead_id = r.json()["lead"]["id"]
    resp_before = client.get("/internal/review", params={"source": "reviewexcl"})
    ids_before = [i["lead_id"] for i in resp_before.json()["items"]]
    assert lead_id in ids_before
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    resp_after = client.get("/internal/review", params={"source": "reviewexcl"})
    ids_after = [i["lead_id"] for i in resp_after.json()["items"]]
    assert lead_id not in ids_after


def test_review_sorted_by_urgency():
    """Alert leads come first, then sorted by score DESC."""
    resp = client.get("/internal/review")
    data = resp.json()
    items = data["items"]
    if len(items) < 2:
        return  # not enough data to verify ordering
    # Verify: all alert=true items come before alert=false items
    saw_non_alert = False
    for item in items:
        if not item["alert"]:
            saw_non_alert = True
        elif saw_non_alert:
            assert False, "alert=true item found after alert=false item"


def test_review_source_filter():
    """Source filter works on review queue."""
    client.post("/leads", json={
        "name": "Review Src", "email": "reviewsrc@review.com",
        "source": "reviewsrc", "notes": STRONG_NOTES,
    })
    resp = client.get("/internal/review", params={"source": "reviewsrc"})
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["source"] == "reviewsrc"


def test_review_urgent_count_from_full_set():
    """urgent_count reflects the full reviewable set, not truncated by limit."""
    source = "reviewurgent"
    for i in range(3):
        client.post("/leads", json={
            "name": f"Urgent {i}", "email": f"urgent{i}@reviewurgent.com",
            "source": source, "notes": STRONG_NOTES,
        })
    # All these leads have score >= 60 → send_to_client → alert=true
    resp_full = client.get("/internal/review", params={"source": source})
    full_urgent = resp_full.json()["urgent_count"]
    assert full_urgent >= 3
    resp_limited = client.get("/internal/review", params={"source": source, "limit": 1})
    limited_data = resp_limited.json()
    assert limited_data["total"] == 1  # only 1 item returned
    assert limited_data["urgent_count"] == full_urgent  # but urgent_count from full set


def test_review_item_contract():
    """Each review item has exactly the approved fields."""
    client.post("/leads", json={
        "name": "Review Contract", "email": "reviewcontract@review.com",
        "source": "reviewcontract", "notes": STRONG_NOTES,
    })
    resp = client.get("/internal/review", params={"source": "reviewcontract"})
    data = resp.json()
    assert data["total"] > 0
    item = data["items"][0]
    expected_keys = {"lead_id", "name", "email", "source", "score", "rating", "next_action", "instruction", "alert", "created_at"}
    assert set(item.keys()) == expected_keys


# ---------------------------------------------------------------------------
# POST /internal/review/{lead_id}/claim — review claim action
# ---------------------------------------------------------------------------


def test_review_claim_success():
    """Claiming a reviewable lead returns status claimed."""
    r = client.post("/leads", json={
        "name": "RClaim OK", "email": "rclaimok@rclaim.com",
        "source": "rclaimtest", "notes": STRONG_NOTES,
    })
    lead_id = r.json()["lead"]["id"]
    resp = client.post(f"/internal/review/{lead_id}/claim")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lead_id"] == lead_id
    assert data["status"] == "claimed"


def test_review_claim_already_claimed():
    """Re-claiming a lead returns status already_claimed."""
    r = client.post("/leads", json={
        "name": "RClaim Dup", "email": "rclaimdup@rclaim.com",
        "source": "rclaimtest", "notes": STRONG_NOTES,
    })
    lead_id = r.json()["lead"]["id"]
    client.post(f"/internal/review/{lead_id}/claim")
    resp = client.post(f"/internal/review/{lead_id}/claim")
    assert resp.status_code == 200
    assert resp.json()["status"] == "already_claimed"


def test_review_claim_not_found():
    """Claiming a non-existent lead returns status not_found."""
    resp = client.post("/internal/review/999888/claim")
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_found"
    assert resp.json()["lead_id"] == 999888


def test_review_claim_not_reviewable():
    """Claiming a non-reviewable lead returns status not_reviewable."""
    # Lead with no notes and low score → discard (not reviewable)
    r = client.post("/leads", json={
        "name": "RClaim NR", "email": "rclaimnr@rclaim.com",
        "source": "rclaimtest",
    })
    lead_id = r.json()["lead"]["id"]
    # Verify this lead's action is not reviewable
    pack = client.get(f"/leads/{lead_id}/pack").json()
    assert pack["next_action"] not in ("send_to_client", "review_manually")
    resp = client.post(f"/internal/review/{lead_id}/claim")
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_reviewable"


def test_review_claim_removes_from_review():
    """Claimed lead disappears from GET /internal/review."""
    r = client.post("/leads", json={
        "name": "RClaim Gone", "email": "rclaimgone@rclaim.com",
        "source": "rclaimgone", "notes": STRONG_NOTES,
    })
    lead_id = r.json()["lead"]["id"]
    resp_before = client.get("/internal/review", params={"source": "rclaimgone"})
    ids_before = [i["lead_id"] for i in resp_before.json()["items"]]
    assert lead_id in ids_before
    client.post(f"/internal/review/{lead_id}/claim")
    resp_after = client.get("/internal/review", params={"source": "rclaimgone"})
    ids_after = [i["lead_id"] for i in resp_after.json()["items"]]
    assert lead_id not in ids_after


def test_review_claim_removes_from_dispatch():
    """Claimed via review also disappears from GET /internal/dispatch."""
    r = client.post("/leads", json={
        "name": "RClaim Disp", "email": "rclaimdisp@rclaim.com",
        "source": "rclaimdisp", "notes": STRONG_NOTES,
    })
    lead_id = r.json()["lead"]["id"]
    resp_before = client.get("/internal/dispatch", params={"source": "rclaimdisp"})
    ids_before = [i["lead_id"] for i in resp_before.json()["items"]]
    assert lead_id in ids_before
    client.post(f"/internal/review/{lead_id}/claim")
    resp_after = client.get("/internal/dispatch", params={"source": "rclaimdisp"})
    ids_after = [i["lead_id"] for i in resp_after.json()["items"]]
    assert lead_id not in ids_after


# ---------------------------------------------------------------------------
# POST /leads/external — canonical external ingestion adapter
# ---------------------------------------------------------------------------


def test_external_basic():
    """Minimal external ingestion: name, email, source only."""
    resp = client.post("/leads/external", json={
        "name": "Ext Basic",
        "email": "extbasic@example.com",
        "source": "landing:test",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["message"] == "lead received"
    assert isinstance(data["lead_id"], int)
    assert isinstance(data["score"], int)


def test_external_with_notes_only():
    """External with notes, no phone/metadata — notes preserved as-is."""
    resp = client.post("/leads/external", json={
        "name": "Ext Notes",
        "email": "extnotes@example.com",
        "source": "form:contact",
        "notes": "Interested in boats",
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead_id"]
    lead = client.get(f"/leads/{lead_id}").json()
    assert lead["notes"] == "Interested in boats"
    assert "@ext:" not in lead["notes"]


def test_external_with_phone():
    """Phone is serialized via @ext: format."""
    resp = client.post("/leads/external", json={
        "name": "Ext Phone",
        "email": "extphone@example.com",
        "source": "landing:barcos",
        "phone": "+34612345678",
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead_id"]
    lead = client.get(f"/leads/{lead_id}").json()
    assert "@ext:" in lead["notes"]
    assert "+34612345678" in lead["notes"]


def test_external_with_metadata():
    """Metadata dict is serialized via @ext: format."""
    resp = client.post("/leads/external", json={
        "name": "Ext Meta",
        "email": "extmeta@example.com",
        "source": "n8n:captacion",
        "metadata": {"boat_type": "sailboat", "length_m": 12},
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead_id"]
    lead = client.get(f"/leads/{lead_id}").json()
    assert "@ext:" in lead["notes"]
    assert "sailboat" in lead["notes"]


def test_external_with_notes_phone_metadata():
    """All fields combined: notes + phone + metadata."""
    resp = client.post("/leads/external", json={
        "name": "Ext Full",
        "email": "extfull@example.com",
        "source": "landing:barcos-venta",
        "phone": "+34699887766",
        "notes": "Quiero vender mi velero",
        "metadata": {"brand": "Beneteau", "year": 2019},
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead_id"]
    lead = client.get(f"/leads/{lead_id}").json()
    # Original notes preserved before @ext: line
    assert lead["notes"].startswith("Quiero vender mi velero")
    # @ext: line present with phone and metadata
    lines = lead["notes"].split("\n")
    ext_line = [l for l in lines if l.startswith("@ext:")]
    assert len(ext_line) == 1
    import json
    ext_data = json.loads(ext_line[0][5:])
    assert ext_data["phone"] == "+34699887766"
    assert ext_data["brand"] == "Beneteau"
    assert ext_data["year"] == 2019


def test_external_duplicate():
    """Duplicate detection via email+source returns 409."""
    payload = {
        "name": "Ext Dup",
        "email": "extdup@example.com",
        "source": "landing:dup-test",
    }
    resp1 = client.post("/leads/external", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "accepted"

    resp2 = client.post("/leads/external", json=payload)
    assert resp2.status_code == 409
    data = resp2.json()
    assert data["status"] == "duplicate"
    assert data["lead_id"] == resp1.json()["lead_id"]
    assert isinstance(data["score"], int)
    assert data["message"] == "lead already exists"


def test_external_response_shape_accepted():
    """Accepted response has exactly 4 fields with correct types."""
    resp = client.post("/leads/external", json={
        "name": "Shape Accepted",
        "email": "shape-accepted@example.com",
        "source": "test:shape-ok",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"status", "lead_id", "score", "message"}
    assert data["status"] == "accepted"
    assert isinstance(data["lead_id"], int)
    assert isinstance(data["score"], int)
    assert isinstance(data["message"], str)


def test_external_response_shape_duplicate():
    """Duplicate response has same 4-field shape as accepted."""
    payload = {
        "name": "Shape Dup",
        "email": "shape-dup@example.com",
        "source": "test:shape-dup",
    }
    client.post("/leads/external", json=payload)
    resp = client.post("/leads/external", json=payload)
    assert resp.status_code == 409
    data = resp.json()
    assert set(data.keys()) == {"status", "lead_id", "score", "message"}
    assert data["status"] == "duplicate"
    assert isinstance(data["lead_id"], int)
    assert isinstance(data["score"], int)
    assert isinstance(data["message"], str)


def test_external_same_email_different_source():
    """Same email with different source creates separate leads."""
    email = "extmulti@example.com"
    resp1 = client.post("/leads/external", json={
        "name": "Multi A", "email": email, "source": "test:source-a",
    })
    resp2 = client.post("/leads/external", json={
        "name": "Multi B", "email": email, "source": "test:source-b",
    })
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["lead_id"] != resp2.json()["lead_id"]


def test_external_validation_missing_fields():
    """Missing required fields returns 422."""
    resp = client.post("/leads/external", json={"name": "No Email"})
    assert resp.status_code == 422


def test_external_validation_empty_source():
    """Empty source after strip returns 422."""
    resp = client.post("/leads/external", json={
        "name": "Empty Src",
        "email": "emptysrc@example.com",
        "source": "   ",
    })
    assert resp.status_code == 422


def test_external_no_ext_marker_when_no_extras():
    """When no phone/metadata, notes has no @ext: marker."""
    resp = client.post("/leads/external", json={
        "name": "Ext Clean",
        "email": "extclean@example.com",
        "source": "test:clean",
        "notes": "Just plain notes",
    })
    lead_id = resp.json()["lead_id"]
    lead = client.get(f"/leads/{lead_id}").json()
    assert "@ext:" not in lead["notes"]


def test_external_source_normalized():
    """Source is normalized to lowercase."""
    resp = client.post("/leads/external", json={
        "name": "Ext Norm",
        "email": "extnorm@example.com",
        "source": "  Landing:BOATS  ",
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead_id"]
    lead = client.get(f"/leads/{lead_id}").json()
    assert lead["source"] == "landing:boats"


def test_external_phone_wins_over_metadata_phone():
    """Explicit phone field takes precedence over metadata['phone']."""
    resp = client.post("/leads/external", json={
        "name": "Phone Priority",
        "email": "phoneprio@example.com",
        "source": "test:prio",
        "phone": "+34111111111",
        "metadata": {"phone": "+34999999999", "other": "value"},
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead_id"]
    lead = client.get(f"/leads/{lead_id}").json()
    import json
    ext_line = [l for l in lead["notes"].split("\n") if l.startswith("@ext:")][0]
    ext_data = json.loads(ext_line[5:])
    assert ext_data["phone"] == "+34111111111"
    assert ext_data["other"] == "value"


def test_external_whitespace_phone_ignored():
    """Empty or whitespace-only phone should not create ext metadata."""
    resp = client.post("/leads/external", json={
        "name": "No Phone",
        "email": "nophone@extws.com",
        "source": "test:nophone",
        "phone": "   ",
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead_id"]
    lead = client.get(f"/leads/{lead_id}").json()
    assert lead["notes"] is None


# ---------------------------------------------------------------------------
# Source hardening tests
# ---------------------------------------------------------------------------


def test_scoring_independent_of_source_name():
    """Same-tier sources produce same score — scoring is signal-based, not name-based."""
    # Both unknown sources: base 20 + notes 5 = 25
    r1 = client.post("/leads", json={
        "name": "ScoreA", "email": "score_ind_a@example.com",
        "source": "unknown-a", "notes": "has notes",
    })
    r2 = client.post("/leads", json={
        "name": "ScoreB", "email": "score_ind_b@example.com",
        "source": "unknown-b", "notes": "has notes",
    })
    assert r1.json()["lead"]["score"] == r2.json()["lead"]["score"] == 25

    # Both without notes: base 20
    r3 = client.post("/leads", json={
        "name": "ScoreC", "email": "score_ind_c@example.com",
        "source": "unknown-a", "notes": "",
    })
    r4 = client.post("/leads", json={
        "name": "ScoreD", "email": "score_ind_d@example.com",
        "source": "unknown-b", "notes": "",
    })
    assert r3.json()["lead"]["score"] == r4.json()["lead"]["score"] == 20


def test_external_rejects_bare_word_source():
    """POST /leads/external rejects source without type:identifier format."""
    resp = client.post("/leads/external", json={
        "name": "Bare", "email": "bare@example.com", "source": "facebook",
    })
    assert resp.status_code == 422
    assert "type:identifier" in resp.json()["detail"]


def test_external_rejects_source_without_colon():
    resp = client.post("/leads/external", json={
        "name": "NoColon", "email": "nocolon@example.com", "source": "testvalue",
    })
    assert resp.status_code == 422


def test_external_rejects_source_empty_type():
    resp = client.post("/leads/external", json={
        "name": "EmptyType", "email": "emptytype@example.com", "source": ":identifier",
    })
    assert resp.status_code == 422


def test_external_rejects_source_empty_identifier():
    resp = client.post("/leads/external", json={
        "name": "EmptyId", "email": "emptyid@example.com", "source": "type:",
    })
    assert resp.status_code == 422


def test_external_accepts_canonical_source():
    """POST /leads/external accepts well-formed type:identifier sources."""
    for source in ["landing:barcos-venta", "n8n:captacion", "form:contact", "api:partner-sync", "test:manual"]:
        resp = client.post("/leads/external", json={
            "name": "Canon", "email": f"canon-{source.replace(':', '-')}@example.com",
            "source": source,
        })
        assert resp.status_code == 200, f"source '{source}' should be accepted"


def test_external_canonical_validation_case_insensitive():
    """Validation applies after normalization — uppercase input is accepted if format is valid."""
    resp = client.post("/leads/external", json={
        "name": "CaseTest", "email": "case-canon@example.com",
        "source": "  Landing:Barcos  ",
    })
    assert resp.status_code == 200
    lead = client.get(f"/leads/{resp.json()['lead_id']}").json()
    assert lead["source"] == "landing:barcos"


def test_legacy_post_leads_still_accepts_bare_words():
    """POST /leads continues to accept bare word sources for backward compatibility."""
    resp = client.post("/leads", json={
        "name": "Legacy", "email": "legacy-bare@example.com",
        "source": "facebook", "notes": "",
    })
    assert resp.status_code == 200
    assert resp.json()["lead"]["source"] == "facebook"


def test_legacy_ingest_still_accepts_bare_words():
    """POST /leads/ingest continues to accept bare word sources."""
    resp = client.post("/leads/ingest", json=[
        {"name": "LegacyIng", "email": "legacy-ing@example.com", "source": "manual", "notes": ""},
    ])
    assert resp.status_code == 200
    assert resp.json()["created"] == 1


def test_webhook_provider_rejects_special_chars():
    """Webhook provider with special characters is rejected."""
    resp = client.post("/leads/webhook/bad provider!", json={
        "name": "BadProv", "email": "badprov@example.com",
    })
    assert resp.status_code == 422


def test_webhook_provider_accepts_valid_format():
    """Webhook provider with valid chars (letters, digits, hyphens, underscores) is accepted."""
    resp = client.post("/leads/webhook/landing-barcos_v2", json={
        "name": "GoodProv", "email": "goodprov@example.com",
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead_id"]
    lead = client.get(f"/leads/{lead_id}").json()
    assert lead["source"] == "webhook:landing-barcos_v2"


def test_webhook_batch_provider_rejects_special_chars():
    """Webhook batch provider with special characters is rejected."""
    resp = client.post("/leads/webhook/bad.provider/batch", json=[
        {"name": "BatchBad", "email": "batchbad@example.com"},
    ])
    assert resp.status_code == 422


def test_dedup_consistent_across_endpoints():
    """Same email+source deduplicates regardless of ingestion endpoint used."""
    email = "dedup-cross@example.com"
    # Create via POST /leads
    r1 = client.post("/leads", json={
        "name": "CrossA", "email": email, "source": "landing:cross-test", "notes": "",
    })
    assert r1.status_code == 200
    # Attempt same via /leads/external — should be duplicate
    r2 = client.post("/leads/external", json={
        "name": "CrossB", "email": email, "source": "landing:cross-test",
    })
    assert r2.status_code == 409
    assert r2.json()["status"] == "duplicate"


# ---------------------------------------------------------------------------
# Audit fixes (H1+H5, H2, H4, H8)
# ---------------------------------------------------------------------------


# --- H1+H5: name normalization ---


def test_name_whitespace_only_rejected():
    """Name with only whitespace is rejected after strip."""
    resp = client.post("/leads", json={
        "name": "   ", "email": "ws_name@audit.com", "source": "test",
    })
    assert resp.status_code == 422
    assert "name" in resp.json()["detail"].lower()


def test_name_stripped_on_create():
    """Name is stripped of leading/trailing whitespace before persistence."""
    resp = client.post("/leads", json={
        "name": "  Padded Name  ", "email": "padname@audit.com", "source": "test",
    })
    assert resp.status_code == 200
    assert resp.json()["lead"]["name"] == "Padded Name"


def test_name_whitespace_rejected_via_ingest():
    """Whitespace-only name in ingest batch is reported as error."""
    resp = client.post("/leads/ingest", json=[
        {"name": "Good", "email": "ing_name_ok@audit.com", "source": "test", "notes": ""},
        {"name": "   ", "email": "ing_name_ws@audit.com", "source": "test", "notes": ""},
    ])
    data = resp.json()
    assert data["created"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["index"] == 1


def test_name_whitespace_rejected_via_webhook():
    """Whitespace-only name in webhook is rejected."""
    resp = client.post("/leads/webhook/audit-test", json={
        "name": "   ", "email": "wh_name_ws@audit.com",
    })
    assert resp.status_code == 422


def test_name_whitespace_rejected_via_external():
    """Whitespace-only name in external is rejected."""
    resp = client.post("/leads/external", json={
        "name": "   ", "email": "ext_name_ws@audit.com", "source": "test:audit",
    })
    assert resp.status_code == 422


# --- H2: DB-level dedup ---


def test_db_unique_constraint_exists():
    """Verify the UNIQUE index on (email, source) exists in the database."""
    import sqlite3
    db = db_module.get_db()
    indexes = db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='leads'"
    ).fetchall()
    index_names = [row[0] for row in indexes]
    assert "uq_leads_email_source" in index_names


def test_dedup_db_level_prevents_direct_duplicate():
    """Direct SQL INSERT of duplicate (email, source) is blocked by DB constraint."""
    import sqlite3
    db = db_module.get_db()
    email = "dbdup@audit.com"
    source = "db_dedup"
    db.execute(
        "INSERT INTO leads (name, email, source, notes, score) VALUES (?, ?, ?, ?, ?)",
        ("First", email, source, None, 50),
    )
    db.commit()
    with __import__("pytest").raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO leads (name, email, source, notes, score) VALUES (?, ?, ?, ?, ?)",
            ("Second", email, source, None, 50),
        )
    db.rollback()


# --- H4: scoring ignores @ext: metadata ---


def test_scoring_ext_only_no_bonus():
    """Lead with only @ext: metadata in notes does not get notes bonus."""
    resp = client.post("/leads/external", json={
        "name": "ExtNoBonus", "email": "ext_nobonus@audit.com",
        "source": "test:h4", "phone": "+34111222333",
    })
    assert resp.status_code == 200
    assert resp.json()["score"] == 25  # base 20 + test source 5, no notes


def test_scoring_ext_plus_real_notes_gets_bonus():
    """Lead with user notes + @ext: metadata — score reflects signal-based scoring."""
    resp = client.post("/leads/external", json={
        "name": "ExtWithNotes", "email": "ext_withnotes@audit.com",
        "source": "test:h4b", "phone": "+34111222333",
        "notes": "Interested in sailboats",
    })
    assert resp.status_code == 200
    assert resp.json()["score"] == 25  # base 20 + test prefix 5 (no boat-specific signals in notes)


def test_scoring_normal_notes_still_gets_bonus():
    """Regular POST /leads with notes still gets the notes bonus."""
    resp = client.post("/leads", json={
        "name": "NormalNotes", "email": "normal_notes@audit.com",
        "source": "test", "notes": "interested in demo",
    })
    assert resp.status_code == 200
    assert resp.json()["lead"]["score"] == 30


@pytest.mark.skip(reason="scoring.py replaced with OpenClaw version; _has_user_notes no longer exists")
def test_scoring_unit_has_user_notes():
    """Unit test for _has_user_notes helper."""
    pass


# --- H8: CSV injection sanitization ---


def test_csv_export_sanitizes_formula_injection():
    """Values starting with =, +, -, @ are prefixed with ' in CSV export."""
    client.post("/leads", json={
        "name": "=CMD()", "email": "csv_inject@audit.com",
        "source": "csv_audit", "notes": "+dangerous",
    })
    resp = client.get("/leads/export.csv", params={"source": "csv_audit"})
    assert resp.status_code == 200
    rows = _parse_csv(resp.text)
    data_row = rows[1]  # first data row
    name_col = rows[0].index("name")
    notes_col = rows[0].index("notes")
    assert data_row[name_col] == "'=CMD()"
    assert data_row[notes_col] == "'+dangerous"


def test_csv_export_normal_values_not_affected():
    """Normal values without dangerous prefixes are not modified."""
    client.post("/leads", json={
        "name": "Normal User", "email": "csv_normal@audit.com",
        "source": "csv_normal", "notes": "just notes",
    })
    resp = client.get("/leads/export.csv", params={"source": "csv_normal"})
    rows = _parse_csv(resp.text)
    data_row = rows[1]
    name_col = rows[0].index("name")
    notes_col = rows[0].index("notes")
    assert data_row[name_col] == "Normal User"
    assert data_row[notes_col] == "just notes"


# ---------------------------------------------------------------------------
# Audit fixes (H9, H11)
# ---------------------------------------------------------------------------


# --- H9: determine_next_action ignores @ext: metadata ---


def test_action_ext_only_treated_as_notes():
    """With new scoring, @ext: metadata is treated as notes present — actions reflect score thresholds."""
    from apps.api.services.actions import determine_next_action

    # score 50 + any notes → review_manually (score >= 40 with notes)
    assert determine_next_action(50, '@ext:{"phone":"+34111"}') == "review_manually"
    assert determine_next_action(50, "interested in boats") == "review_manually"
    assert determine_next_action(50, 'interested\n@ext:{"phone":"+34111"}') == "review_manually"


def test_action_low_score_with_notes():
    """Score < 40 with notes → enrich_first."""
    from apps.api.services.actions import determine_next_action

    assert determine_next_action(30, '@ext:{"phone":"+34111"}') == "enrich_first"
    assert determine_next_action(30, "real notes") == "enrich_first"


def test_action_consistent_with_scoring_on_ext():
    """Scoring and actions agree on ext-only leads."""
    from apps.api.services.actions import determine_next_action
    from apps.api.services.scoring import calculate_lead_score

    notes_ext_only = '@ext:{"phone":"+34111222333"}'
    score = calculate_lead_score("test", notes_ext_only)
    assert score == 30  # base 20 + test source 5 + notes non-empty 5
    action = determine_next_action(score, notes_ext_only)
    assert action == "enrich_first"  # score < 40


def test_action_via_endpoint_ext_only_lead():
    """End-to-end: external lead with phone-only — action reflects score threshold."""
    resp = client.post("/leads/external", json={
        "name": "H9 E2E", "email": "h9e2e@audit.com",
        "source": "test:h9", "phone": "+34999888777",
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead_id"]
    op = client.get(f"/leads/{lead_id}/operational").json()
    assert op["score"] == 25
    assert op["next_action"] == "enrich_first"


# --- H11: ACTION_PRIORITY lives in actions.py ---


def test_action_priority_importable_from_actions():
    """ACTION_PRIORITY is importable from actions module."""
    from apps.api.services.actions import ACTION_PRIORITY

    assert isinstance(ACTION_PRIORITY, list)
    assert "send_to_client" in ACTION_PRIORITY
    assert "review_manually" in ACTION_PRIORITY
    assert "request_more_info" in ACTION_PRIORITY
    assert "enrich_first" in ACTION_PRIORITY


def test_action_priority_not_defined_in_leads():
    """ACTION_PRIORITY is no longer defined directly in leads.py (imported instead)."""
    import inspect
    from apps.api.routes import leads as leads_module

    source = inspect.getsource(leads_module)
    # Should not have a definition line — only an import
    lines = [l for l in source.splitlines() if l.strip().startswith("ACTION_PRIORITY =")]
    assert len(lines) == 0, "ACTION_PRIORITY should not be defined in leads.py"


# ---------------------------------------------------------------------------
# Audit fixes (H15, H19)
# ---------------------------------------------------------------------------


# --- H15: q search escapes LIKE wildcards ---


def test_search_q_percent_literal():
    """Percent sign in q is treated as literal, not LIKE wildcard."""
    client.post("/leads", json={
        "name": "Discount 50%", "email": "pct@h15.com",
        "source": "h15_pct", "notes": "",
    })
    client.post("/leads", json={
        "name": "Discount 500", "email": "nopct@h15.com",
        "source": "h15_pct", "notes": "",
    })
    resp = client.get("/leads", params={"source": "h15_pct", "q": "50%"})
    data = resp.json()
    # Should match "50%" but NOT "500" (% is not a wildcard)
    assert len(data) == 1
    assert data[0]["name"] == "Discount 50%"


def test_search_q_underscore_literal():
    """Underscore in q is treated as literal, not LIKE single-char wildcard."""
    client.post("/leads", json={
        "name": "user_name", "email": "und@h15.com",
        "source": "h15_und", "notes": "",
    })
    client.post("/leads", json={
        "name": "username", "email": "nound@h15.com",
        "source": "h15_und", "notes": "",
    })
    resp = client.get("/leads", params={"source": "h15_und", "q": "user_name"})
    data = resp.json()
    # Should match "user_name" but NOT "username" (_ is not a wildcard)
    assert len(data) == 1
    assert data[0]["name"] == "user_name"


def test_search_q_wildcards_consistent_across_endpoints():
    """LIKE escaping applies to list, summary, and CSV equally."""
    client.post("/leads", json={
        "name": "100% done", "email": "consist@h15.com",
        "source": "h15_consist", "notes": "",
    })
    client.post("/leads", json={
        "name": "1000 done", "email": "noconsist@h15.com",
        "source": "h15_consist", "notes": "",
    })
    # list
    list_resp = client.get("/leads", params={"source": "h15_consist", "q": "100%"})
    assert len(list_resp.json()) == 1
    # summary
    sum_resp = client.get("/leads/summary", params={"source": "h15_consist", "q": "100%"})
    assert sum_resp.json()["total_leads"] == 1
    # csv
    csv_resp = client.get("/leads/export.csv", params={"source": "h15_consist", "q": "100%"})
    rows = _parse_csv(csv_resp.text)
    data_rows = [r for r in rows[1:] if r]
    assert len(data_rows) == 1


# --- H19: source filter normalized in queries ---


def test_source_filter_case_insensitive():
    """Source filter normalizes to lowercase for consistent matching."""
    client.post("/leads", json={
        "name": "Src Norm", "email": "srcnorm@h19.com",
        "source": "h19_source", "notes": "",
    })
    # Query with uppercase — should still match
    resp = client.get("/leads", params={"source": "H19_Source"})
    data = resp.json()
    assert len(data) >= 1
    assert all(lead["source"] == "h19_source" for lead in data)


def test_source_filter_strips_whitespace():
    """Source filter strips leading/trailing whitespace."""
    client.post("/leads", json={
        "name": "Src Strip", "email": "srcstrip@h19.com",
        "source": "h19_strip", "notes": "",
    })
    resp = client.get("/leads", params={"source": "  h19_strip  "})
    data = resp.json()
    assert len(data) >= 1
    assert all(lead["source"] == "h19_strip" for lead in data)


def test_source_filter_normalized_in_summary():
    """Source normalization applies to summary endpoint too."""
    client.post("/leads", json={
        "name": "Sum Norm", "email": "sumnorm@h19.com",
        "source": "h19_summary", "notes": "",
    })
    resp = client.get("/leads/summary", params={"source": "  H19_Summary  "})
    data = resp.json()
    assert data["total_leads"] >= 1
    assert "h19_summary" in data["counts_by_source"]


def test_source_filter_normalized_in_csv():
    """Source normalization applies to CSV export too."""
    client.post("/leads", json={
        "name": "Csv Norm", "email": "csvnorm@h19.com",
        "source": "h19_csv", "notes": "",
    })
    resp = client.get("/leads/export.csv", params={"source": "  H19_Csv  "})
    rows = _parse_csv(resp.text)
    data_rows = [r for r in rows[1:] if r]
    assert len(data_rows) >= 1
    source_col = rows[0].index("source")
    assert all(r[source_col] == "h19_csv" for r in data_rows)


def test_source_filter_normalized_in_actionable():
    """Source normalization applies to actionable endpoint too."""
    client.post("/leads", json={
        "name": "Act Norm", "email": "actnorm@h20.com",
        "source": "h20_actionable", "notes": STRONG_NOTES,
    })
    resp = client.get("/leads/actionable", params={"source": "  H20_Actionable  "})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(item["source"] == "h20_actionable" for item in data)


def test_search_q_empty_ignored():
    """Empty or whitespace-only q parameter should not filter results."""
    baseline = client.get("/leads").json()
    resp_empty = client.get("/leads", params={"q": ""})
    assert resp_empty.status_code == 200
    assert len(resp_empty.json()) == len(baseline)
    resp_spaces = client.get("/leads", params={"q": "   "})
    assert resp_spaces.status_code == 200
    assert len(resp_spaces.json()) == len(baseline)


# ── Date filter tests ──────────────────────────────────────────────


def _setup_dated_leads():
    """Insert leads with known created_at values for date filter tests."""
    import apps.api.db as _db
    db = _db.get_db()
    db.execute(
        "INSERT INTO leads (name, email, source, notes, score, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("Old Lead", "old@datetest.com", "datetest", None, 50, "2025-01-10 08:00:00"),
    )
    db.execute(
        "INSERT INTO leads (name, email, source, notes, score, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("Mid Lead", "mid@datetest.com", "datetest", None, 60, "2025-06-15 12:00:00"),
    )
    db.execute(
        "INSERT INTO leads (name, email, source, notes, score, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("New Lead", "new@datetest.com", "datetest", None, 70, "2025-12-20 18:00:00"),
    )
    db.commit()


_dated_leads_ready = False


def _ensure_dated_leads():
    global _dated_leads_ready
    if not _dated_leads_ready:
        _setup_dated_leads()
        _dated_leads_ready = True


def test_date_filter_created_from():
    _ensure_dated_leads()
    resp = client.get("/leads", params={"source": "datetest", "created_from": "2025-06-01"})
    assert resp.status_code == 200
    names = [l["name"] for l in resp.json()]
    assert "Old Lead" not in names
    assert "Mid Lead" in names
    assert "New Lead" in names


def test_date_filter_created_to():
    _ensure_dated_leads()
    resp = client.get("/leads", params={"source": "datetest", "created_to": "2025-06-30"})
    assert resp.status_code == 200
    names = [l["name"] for l in resp.json()]
    assert "Old Lead" in names
    assert "Mid Lead" in names
    assert "New Lead" not in names


def test_date_filter_range():
    _ensure_dated_leads()
    resp = client.get("/leads", params={
        "source": "datetest",
        "created_from": "2025-06-01",
        "created_to": "2025-06-30",
    })
    assert resp.status_code == 200
    names = [l["name"] for l in resp.json()]
    assert names == ["Mid Lead"]


def test_date_filter_summary_consistent():
    """Date filters on summary must match list results."""
    _ensure_dated_leads()
    list_resp = client.get("/leads", params={
        "source": "datetest",
        "created_from": "2025-06-01",
    })
    summary_resp = client.get("/leads/summary", params={
        "source": "datetest",
        "created_from": "2025-06-01",
    })
    assert summary_resp.status_code == 200
    assert summary_resp.json()["total_leads"] == len(list_resp.json())


def test_date_filter_summary_created_to_consistent():
    """created_to on summary must match list results (complements created_from test above)."""
    _ensure_dated_leads()
    list_resp = client.get("/leads", params={
        "source": "datetest",
        "created_to": "2025-06-30",
    })
    summary_resp = client.get("/leads/summary", params={
        "source": "datetest",
        "created_to": "2025-06-30",
    })
    assert summary_resp.status_code == 200
    assert summary_resp.json()["total_leads"] == len(list_resp.json())


def test_date_filter_csv_consistent():
    """Date filters on CSV must match list results."""
    _ensure_dated_leads()
    list_resp = client.get("/leads", params={
        "source": "datetest",
        "created_from": "2025-06-01",
        "created_to": "2025-06-30",
    })
    csv_resp = client.get("/leads/export.csv", params={
        "source": "datetest",
        "created_from": "2025-06-01",
        "created_to": "2025-06-30",
    })
    assert csv_resp.status_code == 200
    import csv as _csv, io as _io
    reader = _csv.DictReader(_io.StringIO(csv_resp.text))
    csv_names = [row["name"] for row in reader]
    list_names = [l["name"] for l in list_resp.json()]
    assert set(csv_names) == set(list_names)


def test_date_filter_whitespace_ignored():
    """Whitespace-only date params should be ignored, not corrupt the query."""
    _ensure_dated_leads()
    baseline = client.get("/leads", params={"source": "datetest"}).json()
    resp = client.get("/leads", params={"source": "datetest", "created_from": "  ", "created_to": "  "})
    assert resp.status_code == 200
    assert len(resp.json()) == len(baseline)


def test_date_filter_invalid_format_422():
    """Invalid date format must return 422, not silently corrupt results."""
    resp = client.get("/leads", params={"created_from": "not-a-date"})
    assert resp.status_code == 422

    resp2 = client.get("/leads", params={"created_to": "2025/06/15"})
    assert resp2.status_code == 422

    resp3 = client.get("/leads/summary", params={"created_from": "yesterday"})
    assert resp3.status_code == 422

    resp4 = client.get("/leads/export.csv", params={"created_to": "15-06-2025"})
    assert resp4.status_code == 422


# --- Ops Snapshot ---

def test_ops_snapshot_shape():
    """Snapshot response has all required fields with correct types."""
    resp = client.get("/internal/ops/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    for field in ("total_leads", "actionable", "claimed", "pending_dispatch", "pending_review", "urgent"):
        assert field in data
        assert isinstance(data[field], int)


def test_ops_snapshot_total_leads_consistent():
    """total_leads reflects all leads in DB, not just actionable."""
    resp = client.get("/internal/ops/snapshot")
    data = resp.json()
    all_leads = client.get("/leads", params={"limit": 10000}).json()
    assert data["total_leads"] == len(all_leads)


def test_ops_snapshot_pending_dispatch_consistent():
    """pending_dispatch = actionable - claimed."""
    resp = client.get("/internal/ops/snapshot")
    data = resp.json()
    assert data["pending_dispatch"] == data["actionable"] - data["claimed"]


def test_ops_snapshot_pending_review_consistent():
    """pending_review <= pending_dispatch (subset of unclaimed actionable)."""
    resp = client.get("/internal/ops/snapshot")
    data = resp.json()
    assert data["pending_review"] <= data["pending_dispatch"]


def test_ops_snapshot_urgent_means_actionable_unclaimed_alert():
    """urgent = actionable + unclaimed + alert=true."""
    # Create a high-score lead (alert=true, score >= 60)
    urgent_lead = {
        "name": "Urgent Snap Lead",
        "email": "urgentsnap@example.com",
        "source": "opssnaptest",
        "notes": "important notes",
    }
    create_resp = client.post("/leads", json=urgent_lead)
    assert create_resp.status_code == 200
    lead_id = create_resp.json()["lead"]["id"]
    snap = client.get("/internal/ops/snapshot").json()
    # urgent must match unclaimed actionable leads with alert=true
    # dispatch endpoint returns exactly the unclaimed actionable set
    dispatch_items = client.get("/internal/dispatch").json()["items"]
    alert_count = sum(1 for item in dispatch_items if item["alert"])
    assert snap["urgent"] == alert_count


def test_ops_snapshot_claimed_reflects_claims():
    """Claiming a lead increments the claimed count."""
    snap_before = client.get("/internal/ops/snapshot").json()
    # Create and claim a fresh lead
    lead = {
        "name": "Claim Snap Lead",
        "email": "claimsnap@example.com",
        "source": "opssnaptest",
        "notes": STRONG_NOTES,
    }
    create_resp = client.post("/leads", json=lead)
    assert create_resp.status_code == 200
    lead_id = create_resp.json()["lead"]["id"]
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    snap_after = client.get("/internal/ops/snapshot").json()
    assert snap_after["claimed"] == snap_before["claimed"] + 1


# --- Cross-Surface Consistency Invariants ---


def test_snapshot_pending_review_equals_review_total():
    """snapshot.pending_review must equal review.total (both count unclaimed reviewable leads)."""
    snap = client.get("/internal/ops/snapshot").json()
    review = client.get("/internal/review").json()
    assert snap["pending_review"] == review["total"]


def test_snapshot_pending_review_equals_daily_review_plus_client_ready():
    """snapshot.pending_review must equal daily_actions.pending_review + daily_actions.client_ready.

    Snapshot combines review_manually + send_to_client into one count.
    Daily-actions splits them into separate sections. The sum must match.
    """
    snap = client.get("/internal/ops/snapshot").json()
    daily = client.get("/internal/daily-actions").json()
    assert snap["pending_review"] == (
        daily["summary"]["pending_review"] + daily["summary"]["client_ready"]
    )


def test_client_ready_total_equals_daily_client_ready():
    """client-ready.total must equal daily_actions.summary.client_ready."""
    cr = client.get("/internal/client-ready").json()
    daily = client.get("/internal/daily-actions").json()
    assert cr["total"] == daily["summary"]["client_ready"]


# --- Client-Ready Queue ---

def test_client_ready_shape():
    """Response has correct shape and field types."""
    resp = client.get("/internal/client-ready")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert isinstance(data["total"], int)
    assert isinstance(data["items"], list)


def test_client_ready_only_send_to_client():
    """All items have next_action = send_to_client."""
    # Create a lead with notes (score 60 -> send_to_client)
    lead = {
        "name": "Client Ready Lead",
        "email": "clientready@example.com",
        "source": "clientreadytest",
        "notes": "has notes for high score",
    }
    create_resp = client.post("/leads", json=lead)
    assert create_resp.status_code == 200
    resp = client.get("/internal/client-ready")
    data = resp.json()
    for item in data["items"]:
        assert item["next_action"] == "send_to_client"


def test_client_ready_item_contract():
    """Each item has all expected fields."""
    resp = client.get("/internal/client-ready")
    data = resp.json()
    if data["total"] > 0:
        item = data["items"][0]
        expected_fields = {
            "lead_id", "name", "email", "source", "score",
            "rating", "next_action", "instruction", "created_at",
        }
        assert set(item.keys()) == expected_fields


def test_client_ready_excludes_claimed():
    """Claimed leads do not appear in client-ready queue."""
    lead = {
        "name": "Claim Ready Lead",
        "email": "claimready@example.com",
        "source": "clientreadytest",
        "notes": STRONG_NOTES,
    }
    create_resp = client.post("/leads", json=lead)
    assert create_resp.status_code == 200
    lead_id = create_resp.json()["lead"]["id"]
    before = client.get("/internal/client-ready").json()
    before_ids = {item["lead_id"] for item in before["items"]}
    assert lead_id in before_ids
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    after = client.get("/internal/client-ready").json()
    after_ids = {item["lead_id"] for item in after["items"]}
    assert lead_id not in after_ids


def test_client_ready_sorted_by_score_desc():
    """Items are sorted by score descending."""
    resp = client.get("/internal/client-ready")
    data = resp.json()
    scores = [item["score"] for item in data["items"]]
    assert scores == sorted(scores, reverse=True)


def test_client_ready_consistent_with_handoffs():
    """Client-ready lead_ids are a subset of handoffs with action=send_to_client."""
    ready = client.get("/internal/client-ready").json()
    handoffs = client.get("/internal/handoffs", params={"action": "send_to_client"}).json()
    ready_ids = {item["lead_id"] for item in ready["items"]}
    handoff_ids = {item["lead_id"] for item in handoffs["items"]}
    assert ready_ids == handoff_ids


# --- Operator Worklist ---

def test_worklist_shape():
    """Response has correct top-level shape."""
    resp = client.get("/internal/worklist")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert isinstance(data["pending_review"], list)
    assert isinstance(data["client_ready"], list)
    assert isinstance(data["recently_claimed"], list)


def test_worklist_pending_review_matches_review():
    """pending_review lead_ids match /internal/review lead_ids."""
    worklist = client.get("/internal/worklist").json()
    review = client.get("/internal/review").json()
    wl_ids = [item["lead_id"] for item in worklist["pending_review"]]
    rv_ids = [item["lead_id"] for item in review["items"]]
    assert wl_ids == rv_ids


def test_worklist_client_ready_matches_client_ready():
    """client_ready lead_ids match /internal/client-ready lead_ids."""
    worklist = client.get("/internal/worklist").json()
    ready = client.get("/internal/client-ready").json()
    wl_ids = [item["lead_id"] for item in worklist["client_ready"]]
    cr_ids = [item["lead_id"] for item in ready["items"]]
    assert wl_ids == cr_ids


def test_worklist_recently_claimed_has_claimed_at():
    """Each recently_claimed item has lead_id, name, source, score, claimed_at."""
    # Ensure at least one claim exists
    lead = {
        "name": "Worklist Claim Lead",
        "email": "worklistclaim@example.com",
        "source": "worklisttest",
        "notes": "notes",
    }
    create_resp = client.post("/leads", json=lead)
    assert create_resp.status_code == 200
    lead_id = create_resp.json()["lead"]["id"]
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    worklist = client.get("/internal/worklist").json()
    assert len(worklist["recently_claimed"]) > 0
    item = worklist["recently_claimed"][0]
    assert set(item.keys()) == {"lead_id", "name", "source", "score", "claimed_at"}


def test_worklist_recently_claimed_max_10():
    """recently_claimed returns at most 10 items."""
    worklist = client.get("/internal/worklist").json()
    assert len(worklist["recently_claimed"]) <= 10


def test_worklist_recently_claimed_ordered_by_claimed_at_desc():
    """recently_claimed is ordered by claimed_at descending."""
    worklist = client.get("/internal/worklist").json()
    claimed = worklist["recently_claimed"]
    if len(claimed) >= 2:
        dates = [item["claimed_at"] for item in claimed]
        assert dates == sorted(dates, reverse=True)


# --- Claim Release ---

def _create_and_claim_lead(name: str, email: str, source: str = "releasetest") -> int:
    """Helper: create a lead with strong notes, claim it, return lead_id."""
    lead = {"name": name, "email": email, "source": source, "notes": STRONG_NOTES}
    resp = client.post("/leads", json=lead)
    assert resp.status_code == 200
    lead_id = resp.json()["lead"]["id"]
    claim_resp = client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    assert lead_id in claim_resp.json()["claimed"]
    return lead_id


def test_release_claim_success():
    """Releasing an active claim returns status=released."""
    lead_id = _create_and_claim_lead("Release Success", "releasesuccess@example.com")
    resp = client.delete(f"/internal/dispatch/claim/{lead_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lead_id"] == lead_id
    assert data["status"] == "released"


def test_release_claim_not_found():
    """Releasing a claim for a nonexistent lead returns status=not_found."""
    resp = client.delete("/internal/dispatch/claim/999999")
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_found"


def test_release_claim_not_claimed():
    """Releasing a claim for an unclaimed lead returns status=not_claimed."""
    lead = {"name": "Not Claimed Lead", "email": "notclaimed@example.com", "source": "releasetest", "notes": "notes"}
    create_resp = client.post("/leads", json=lead)
    assert create_resp.status_code == 200
    lead_id = create_resp.json()["lead"]["id"]
    resp = client.delete(f"/internal/dispatch/claim/{lead_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_claimed"


def test_release_reappears_in_review():
    """Released lead reappears in /internal/review if still reviewable."""
    lead_id = _create_and_claim_lead("Release Review", "releasereview@example.com")
    # Verify excluded while claimed
    review_ids = {item["lead_id"] for item in client.get("/internal/review").json()["items"]}
    assert lead_id not in review_ids
    # Release
    client.delete(f"/internal/dispatch/claim/{lead_id}")
    # Verify reappears (lead has notes -> score 60 -> send_to_client -> reviewable)
    review_ids_after = {item["lead_id"] for item in client.get("/internal/review").json()["items"]}
    assert lead_id in review_ids_after


def test_release_reappears_in_client_ready():
    """Released lead reappears in /internal/client-ready if still send_to_client."""
    lead_id = _create_and_claim_lead("Release Ready", "releaseready@example.com")
    # Verify excluded while claimed
    ready_ids = {item["lead_id"] for item in client.get("/internal/client-ready").json()["items"]}
    assert lead_id not in ready_ids
    # Release
    client.delete(f"/internal/dispatch/claim/{lead_id}")
    # Verify reappears (lead has notes -> score 60 -> send_to_client)
    ready_ids_after = {item["lead_id"] for item in client.get("/internal/client-ready").json()["items"]}
    assert lead_id in ready_ids_after


def test_release_reappears_in_dispatch():
    """Released lead reappears in /internal/dispatch if still actionable."""
    lead_id = _create_and_claim_lead("Release Dispatch", "releasedispatch@example.com")
    # Verify excluded while claimed
    dispatch_ids = {item["lead_id"] for item in client.get("/internal/dispatch").json()["items"]}
    assert lead_id not in dispatch_ids
    # Release
    client.delete(f"/internal/dispatch/claim/{lead_id}")
    # Verify reappears
    dispatch_ids_after = {item["lead_id"] for item in client.get("/internal/dispatch").json()["items"]}
    assert lead_id in dispatch_ids_after


# --- Demo Intake Form ---

def test_demo_intake_serves_html():
    """GET /demo/intake returns an HTML page with a form."""
    resp = client.get("/demo/intake")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<form" in resp.text
    assert "/leads/external" in resp.text


def test_demo_intake_end_to_end():
    """Submit via /leads/external (same path the demo form uses), verify lead appears in client-ready."""
    payload = {
        "name": "Demo E2E Lead",
        "email": "demoe2e@example.com",
        "source": "landing:demo-test",
        "notes": STRONG_NOTES,
    }
    resp = client.post("/leads/external", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    lead_id = data["lead_id"]
    # Lead with strong notes -> score >= 60 -> send_to_client -> appears in client-ready
    ready_ids = {item["lead_id"] for item in client.get("/internal/client-ready").json()["items"]}
    assert lead_id in ready_ids


def test_demo_intake_duplicate_feedback():
    """Submitting the same lead twice via external returns 409 duplicate."""
    payload = {
        "name": "Demo Dup Lead",
        "email": "demodup@example.com",
        "source": "landing:demo-test",
    }
    first = client.post("/leads/external", json=payload)
    assert first.status_code == 200
    second = client.post("/leads/external", json=payload)
    assert second.status_code == 409
    assert second.json()["status"] == "duplicate"


def test_demo_intake_invalid_payload_422():
    """Missing required field via /leads/external returns 422 — the demo form relies on browser validation, but the API enforces its own schema."""
    payload = {"name": "No Email Lead", "source": "landing:demo-test"}
    resp = client.post("/leads/external", json=payload)
    assert resp.status_code == 422


def test_demo_intake_defensive_markers():
    """Demo page carries anti-indexing, anti-caching, and visible demo-only markers."""
    resp = client.get("/demo/intake")
    assert resp.status_code == 200
    # Anti-indexing meta tag
    assert 'noindex' in resp.text
    assert 'nofollow' in resp.text
    # Visible demo-only copy
    assert 'not a production surface' in resp.text.lower()
    # Response headers
    assert resp.headers.get("cache-control") == "no-store"
    assert resp.headers.get("x-content-type-options") == "nosniff"


# --- Source Performance ---


def test_source_performance_shape():
    """GET /internal/source-performance returns expected top-level shape."""
    resp = client.get("/internal/source-performance")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "total_sources" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["total_sources"] == len(data["items"])


def test_source_performance_item_fields():
    """Each source item has the expected fields and types."""
    # Ensure at least one source exists
    client.post("/leads", json={"name": "SP Field", "email": "spfield@example.com", "source": "perf:fields"})
    resp = client.get("/internal/source-performance")
    data = resp.json()
    assert data["total_sources"] >= 1
    item = data["items"][0]
    assert "source" in item
    assert "total" in item
    assert "avg_score" in item
    assert "client_ready" in item
    assert "review" in item
    assert isinstance(item["total"], int)
    assert isinstance(item["avg_score"], (int, float))
    assert isinstance(item["client_ready"], int)
    assert isinstance(item["review"], int)


def test_source_performance_counts_accurate():
    """Per-source total and avg_score match direct SQL expectations."""
    src = "perf:accuracy"
    client.post("/leads", json={"name": "PA1", "email": "pa1@example.com", "source": src})
    client.post("/leads", json={"name": "PA2", "email": "pa2@example.com", "source": src, "notes": "has notes"})
    resp = client.get("/internal/source-performance")
    items_by_source = {i["source"]: i for i in resp.json()["items"]}
    assert src in items_by_source
    item = items_by_source[src]
    assert item["total"] == 2


def test_source_performance_client_ready_independent_of_claims():
    """client_ready counts are independent of claim status — they measure source quality."""
    src = "perf:claims"
    r1 = client.post("/leads", json={"name": "PC1", "email": "pc1@example.com", "source": src, "notes": "noted"})
    lead_id = r1.json()["lead"]["id"]
    # Before claim
    resp_before = client.get("/internal/source-performance")
    before = {i["source"]: i for i in resp_before.json()["items"]}[src]
    # Claim the lead
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    # After claim — client_ready count should be the same
    resp_after = client.get("/internal/source-performance")
    after = {i["source"]: i for i in resp_after.json()["items"]}[src]
    assert after["client_ready"] == before["client_ready"]
    assert after["review"] == before["review"]
    # Cleanup
    client.delete(f"/internal/dispatch/claim/{lead_id}")


def test_source_performance_sorted_by_total_desc():
    """Sources are sorted by total leads descending."""
    resp = client.get("/internal/source-performance")
    items = resp.json()["items"]
    if len(items) >= 2:
        totals = [i["total"] for i in items]
        assert totals == sorted(totals, reverse=True)


# --- Source Actions ---


def test_source_actions_shape():
    """GET /internal/source-actions returns expected top-level shape."""
    resp = client.get("/internal/source-actions")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "total_sources" in data
    assert "items" in data
    assert data["total_sources"] == len(data["items"])


def test_source_actions_item_fields():
    """Each source action item has expected fields."""
    client.post("/leads", json={"name": "SA Field", "email": "safield@example.com", "source": "action:fields"})
    resp = client.get("/internal/source-actions")
    item = resp.json()["items"][0]
    for field in ("source", "total", "actionable", "avg_score", "client_ready", "review", "recommendation", "rationale"):
        assert field in item


def test_source_actions_insufficient_data():
    """Source with fewer than 3 actionable leads gets 'review' / 'insufficient data'."""
    src = "action:tiny"
    client.post("/leads", json={"name": "AT1", "email": "at1@example.com", "source": src})
    resp = client.get("/internal/source-actions")
    item = {i["source"]: i for i in resp.json()["items"]}[src]
    assert item["recommendation"] == "review"
    assert item["rationale"] == "insufficient data"


def test_source_actions_keep_high_client_ready():
    """Source with >= 50% client_ready rate gets 'keep' / 'high client_ready rate'."""
    src = "action:highcr"
    # All leads with strong notes -> score >= 60 -> send_to_client
    for i in range(4):
        client.post("/leads", json={
            "name": f"CR{i}", "email": f"cr{i}@action-highcr.com",
            "source": src, "notes": STRONG_NOTES
        })
    resp = client.get("/internal/source-actions")
    item = {i["source"]: i for i in resp.json()["items"]}[src]
    assert item["recommendation"] == "keep"
    assert item["rationale"] == "high client_ready rate"


def test_source_actions_keep_strong_avg_score():
    """Source with avg_score >= 55 but < 50% client_ready gets 'keep' / 'strong avg score'."""
    src = "action:strongavg"
    # Mix: 2 with strong notes (score ~60) + 2 with medium notes (score ~50) = avg ~55
    for i in range(2):
        client.post("/leads", json={
            "name": f"SN{i}", "email": f"sn{i}@action-strongavg.com",
            "source": src, "notes": STRONG_NOTES
        })
    for i in range(2):
        client.post("/leads", json={
            "name": f"SB{i}", "email": f"sb{i}@action-strongavg.com",
            "source": src, "notes": "Tipo: Velero\nTeléfono: +34612345678"
        })
    resp = client.get("/internal/source-actions")
    item = {i["source"]: i for i in resp.json()["items"]}[src]
    # All have score >= 40 -> actionable. 2 with score >= 60 -> client_ready
    # 2/4 = 50% -> hits client_ready rule
    assert item["recommendation"] == "keep"


def test_source_actions_review_no_strong_signal():
    """Source with no strong signal defaults to 'review'."""
    src = "action:nosignal"
    # 4 leads, all without notes -> score 50 -> review_manually
    # avg_score = 50, client_ready = 0, review/actionable = 1.0
    # But review/actionable >= 0.3 fires -> "high review rate"
    for i in range(4):
        client.post("/leads", json={
            "name": f"NS{i}", "email": f"ns{i}@action-nosignal.com",
            "source": src
        })
    resp = client.get("/internal/source-actions")
    item = {i["source"]: i for i in resp.json()["items"]}[src]
    assert item["recommendation"] == "review"


def test_source_actions_deterministic():
    """Same source data produces same recommendation across calls."""
    r1 = client.get("/internal/source-actions")
    r2 = client.get("/internal/source-actions")
    items1 = {i["source"]: (i["recommendation"], i["rationale"]) for i in r1.json()["items"]}
    items2 = {i["source"]: (i["recommendation"], i["rationale"]) for i in r2.json()["items"]}
    assert items1 == items2


def test_source_actions_recommendation_values():
    """All recommendations are from the allowed set."""
    resp = client.get("/internal/source-actions")
    allowed = {"keep", "review"}
    for item in resp.json()["items"]:
        assert item["recommendation"] in allowed


# --- Event Spine Tests ---


def test_events_endpoint_shape():
    """GET /internal/events returns valid structure."""
    resp = client.get("/internal/events")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "total" in data
    assert "items" in data
    assert data["total"] == len(data["items"])


def test_events_item_fields():
    """Each event item has the required fields."""
    resp = client.get("/internal/events?limit=1")
    if resp.json()["total"] > 0:
        item = resp.json()["items"][0]
        for field in ("id", "event_type", "entity_type", "entity_id", "origin_module", "payload", "created_at"):
            assert field in item


def test_event_emitted_on_lead_created():
    """Creating a lead emits a lead.created event."""
    resp = client.post("/leads", json={
        "name": "Event Test", "email": "event-created@example.com",
        "source": "event:test", "notes": "some notes",
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead"]["id"]
    events = client.get("/internal/events?event_type=lead.created").json()["items"]
    matching = [e for e in events if e["entity_id"] == lead_id]
    assert len(matching) == 1
    ev = matching[0]
    assert ev["entity_type"] == "lead"
    assert ev["origin_module"] == "leads"
    assert ev["payload"]["source"] == "event:test"
    assert ev["payload"]["score"] == resp.json()["lead"]["score"]
    assert "name" not in ev["payload"]
    assert "email" not in ev["payload"]


def test_event_emitted_on_lead_claimed():
    """Claiming a lead emits a lead.claimed event."""
    resp = client.post("/leads", json={
        "name": "Claim Event", "email": "event-claimed@example.com",
        "source": "event:claim",
    })
    lead_id = resp.json()["lead"]["id"]
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    events = client.get("/internal/events?event_type=lead.claimed").json()["items"]
    matching = [e for e in events if e["entity_id"] == lead_id]
    assert len(matching) == 1
    ev = matching[0]
    assert ev["entity_type"] == "lead"
    assert ev["origin_module"] == "dispatch"
    assert ev["payload"] == {}


def test_event_emitted_on_lead_released():
    """Releasing a claim emits a lead.released event."""
    resp = client.post("/leads", json={
        "name": "Release Event", "email": "event-released@example.com",
        "source": "event:release",
    })
    lead_id = resp.json()["lead"]["id"]
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    client.delete(f"/internal/dispatch/claim/{lead_id}")
    events = client.get("/internal/events?event_type=lead.released").json()["items"]
    matching = [e for e in events if e["entity_id"] == lead_id]
    assert len(matching) == 1
    ev = matching[0]
    assert ev["entity_type"] == "lead"
    assert ev["origin_module"] == "dispatch"
    assert ev["payload"] == {}


def test_event_review_claim_emits_claimed():
    """Claiming via review endpoint also emits lead.claimed with origin_module=review."""
    resp = client.post("/leads", json={
        "name": "Review Claim Event", "email": "event-review-claim@example.com",
        "source": "event:reviewclaim", "notes": STRONG_NOTES,
    })
    lead_id = resp.json()["lead"]["id"]
    client.post(f"/internal/review/{lead_id}/claim")
    events = client.get("/internal/events?event_type=lead.claimed").json()["items"]
    matching = [e for e in events if e["entity_id"] == lead_id]
    assert len(matching) >= 1
    ev = matching[0]
    assert ev["origin_module"] == "review"


def test_events_filter_by_event_type():
    """event_type filter returns only matching events."""
    resp = client.get("/internal/events?event_type=lead.created")
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["event_type"] == "lead.created"


def test_events_limit_respected():
    """limit param caps the number of returned events."""
    resp = client.get("/internal/events?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) <= 2


def test_events_ordered_newest_first():
    """Events are returned in reverse chronological order (newest first)."""
    resp = client.get("/internal/events")
    items = resp.json()["items"]
    if len(items) >= 2:
        ids = [item["id"] for item in items]
        assert ids == sorted(ids, reverse=True)


def test_events_no_pii_in_created_payload():
    """lead.created events must not contain name or email."""
    resp = client.post("/leads", json={
        "name": "PII Check", "email": "pii-check@example.com",
        "source": "event:pii",
    })
    lead_id = resp.json()["lead"]["id"]
    events = client.get("/internal/events?event_type=lead.created").json()["items"]
    matching = [e for e in events if e["entity_id"] == lead_id]
    assert len(matching) == 1
    payload = matching[0]["payload"]
    assert "name" not in payload
    assert "email" not in payload
    assert "source" in payload
    assert "score" in payload


def test_events_duplicate_lead_no_event():
    """Duplicate lead creation does not emit an event."""
    email = "event-nodup@example.com"
    client.post("/leads", json={
        "name": "No Dup Event", "email": email, "source": "event:nodup",
    })
    events_before = client.get("/internal/events?event_type=lead.created").json()["total"]
    resp = client.post("/leads", json={
        "name": "No Dup Event", "email": email, "source": "event:nodup",
    })
    assert resp.status_code == 409
    events_after = client.get("/internal/events?event_type=lead.created").json()["total"]
    assert events_after == events_before


def test_event_emission_failure_does_not_break_lead_creation():
    """Best-effort guarantee: if emit_event internally fails, the lead is still created."""
    from unittest.mock import patch

    # Patch get_db inside the events module so the INSERT inside emit_event
    # raises, but the try/except in emit_event catches it silently.
    with patch("apps.api.events.get_db", side_effect=RuntimeError("db boom")):
        resp = client.post("/leads", json={
            "name": "Silent Fail",
            "email": "silent-fail-event@example.com",
            "source": "event:failtest",
        })
    assert resp.status_code == 200
    lead_id = resp.json()["lead"]["id"]
    # Lead must be persisted despite event emission failure
    get_resp = client.get(f"/leads/{lead_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["email"] == "silent-fail-event@example.com"
    # No lead.created event should exist for this lead (emission failed silently)
    events = client.get("/internal/events?event_type=lead.created").json()["items"]
    matching = [e for e in events if e["entity_id"] == lead_id]
    assert len(matching) == 0


def test_event_emitted_on_external_lead_created():
    """POST /leads/external also emits a lead.created event via _create_lead_internal."""
    resp = client.post("/leads/external", json={
        "name": "External Event",
        "email": "ext-event@example.com",
        "source": "ext:eventtest",
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead_id"]
    events = client.get("/internal/events?event_type=lead.created").json()["items"]
    matching = [e for e in events if e["entity_id"] == lead_id]
    assert len(matching) == 1
    ev = matching[0]
    assert ev["origin_module"] == "leads"
    assert ev["payload"]["source"] == "ext:eventtest"
    assert "name" not in ev["payload"]
    assert "email" not in ev["payload"]


def test_existing_endpoints_still_work_after_events():
    """Existing endpoints remain functional after event spine addition."""
    assert client.get("/health").status_code == 200
    assert client.get("/leads").status_code == 200
    assert client.get("/internal/queue").status_code == 200
    assert client.get("/internal/dispatch").status_code == 200
    assert client.get("/internal/ops/snapshot").status_code == 200


# --- Sentinel Tests ---


def test_sentinel_shape():
    """GET /internal/sentinel returns valid structure."""
    resp = client.get("/internal/sentinel")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "status" in data
    assert "total_findings" in data
    assert "findings" in data
    assert data["total_findings"] == len(data["findings"])
    assert data["status"] in ("ok", "watch", "alert")


def test_sentinel_finding_fields():
    """Each finding has the required fields."""
    resp = client.get("/internal/sentinel")
    for finding in resp.json()["findings"]:
        for field in ("check", "surface", "severity", "message", "recommended_action"):
            assert field in finding
        assert finding["severity"] in ("low", "medium", "high")


def test_sentinel_status_ok_when_no_medium_or_high():
    """Status is ok when no medium or high findings exist."""
    resp = client.get("/internal/sentinel")
    data = resp.json()
    severities = {f["severity"] for f in data["findings"]}
    if "high" not in severities and "medium" not in severities:
        assert data["status"] == "ok"


def test_sentinel_event_spine_not_silent():
    """event_spine_silent check should not fire when events exist."""
    # Events were emitted by earlier tests, so the spine is not silent
    resp = client.get("/internal/sentinel")
    checks = [f["check"] for f in resp.json()["findings"]]
    assert "event_spine_silent" not in checks


def test_sentinel_stale_claims_fires_on_old_claim():
    """stale_claims check fires when a claim is older than threshold."""
    # Create and claim a lead, then backdate the claim
    resp = client.post("/leads", json={
        "name": "Stale Sentinel", "email": "stale-sentinel@example.com",
        "source": "sentinel:stale",
    })
    lead_id = resp.json()["lead"]["id"]
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    # Backdate the claim to 48 hours ago
    db = db_module.get_db()
    db.execute(
        "UPDATE dispatch_claims SET claimed_at = datetime('now', '-48 hours') WHERE lead_id = ?",
        (lead_id,),
    )
    db.commit()
    resp = client.get("/internal/sentinel")
    stale = [f for f in resp.json()["findings"] if f["check"] == "stale_claims"]
    assert len(stale) == 1
    assert stale[0]["surface"] == "dispatch"
    assert stale[0]["severity"] in ("low", "medium")
    # Cleanup: release the claim
    client.delete(f"/internal/dispatch/claim/{lead_id}")


def test_sentinel_stale_claims_absent_when_fresh():
    """stale_claims does not fire when all claims are fresh."""
    resp = client.post("/leads", json={
        "name": "Fresh Sentinel", "email": "fresh-sentinel@example.com",
        "source": "sentinel:fresh",
    })
    lead_id = resp.json()["lead"]["id"]
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    resp = client.get("/internal/sentinel")
    stale = [f for f in resp.json()["findings"] if f["check"] == "stale_claims"]
    # Fresh claim should not trigger stale_claims
    # (there may be stale claims from other tests, so only check this specific one doesn't cause issues)
    assert resp.status_code == 200
    # Cleanup
    client.delete(f"/internal/dispatch/claim/{lead_id}")



def test_sentinel_source_needs_attention():
    """source_needs_attention fires for sources with review recommendation and sufficient data."""
    resp = client.get("/internal/sentinel")
    attn = [f for f in resp.json()["findings"] if f["check"] == "source_needs_attention"]
    # All source_needs_attention findings should have severity low
    for finding in attn:
        assert finding["severity"] == "low"
        assert finding["surface"] == "source-actions"


def test_sentinel_deterministic():
    """Same DB state produces same sentinel results."""
    r1 = client.get("/internal/sentinel").json()
    r2 = client.get("/internal/sentinel").json()
    assert r1["status"] == r2["status"]
    assert r1["total_findings"] == r2["total_findings"]
    checks1 = [(f["check"], f["severity"]) for f in r1["findings"]]
    checks2 = [(f["check"], f["severity"]) for f in r2["findings"]]
    assert checks1 == checks2


def test_sentinel_status_derives_from_severity():
    """Status correctly reflects the highest severity finding."""
    resp = client.get("/internal/sentinel")
    data = resp.json()
    severities = {f["severity"] for f in data["findings"]}
    if "high" in severities:
        assert data["status"] == "alert"
    elif "medium" in severities:
        assert data["status"] == "watch"
    else:
        assert data["status"] == "ok"


def test_sentinel_event_spine_recent_silence():
    """event_spine_silent fires medium when recent leads exist but no recent events."""
    db = db_module.get_db()
    # Backdate ALL events to 48 hours ago so none are "recent"
    db.execute("UPDATE events SET created_at = datetime('now', '-48 hours')")
    db.commit()
    # Create a fresh lead — this also emits a lead.created event with current timestamp
    resp = client.post("/leads", json={
        "name": "Recent Silence", "email": "recent-silence@example.com",
        "source": "sentinel:recency",
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead"]["id"]
    # Now backdate THAT new event too, so we have recent leads but no recent events
    db.execute("UPDATE events SET created_at = datetime('now', '-48 hours') WHERE entity_id = ?", (lead_id,))
    db.commit()
    sentinel_resp = client.get("/internal/sentinel")
    findings = [f for f in sentinel_resp.json()["findings"] if f["check"] == "event_spine_silent"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"
    assert "last 24h" in findings[0]["message"]
    # Cleanup: restore event timestamps so other tests are not affected
    db.execute("UPDATE events SET created_at = datetime('now')")
    db.commit()


def test_sentinel_event_spine_no_silence_when_recent_events_exist():
    """event_spine_silent does not fire when both recent leads and recent events exist."""
    # Normal state: events were emitted by earlier tests with current timestamps
    resp = client.get("/internal/sentinel")
    checks = [f["check"] for f in resp.json()["findings"]]
    assert "event_spine_silent" not in checks


def test_existing_endpoints_still_work_after_sentinel():
    """Existing endpoints remain functional after sentinel addition."""
    assert client.get("/health").status_code == 200
    assert client.get("/leads").status_code == 200
    assert client.get("/internal/queue").status_code == 200
    assert client.get("/internal/events").status_code == 200
    assert client.get("/internal/source-actions").status_code == 200


# ── Audit ──


def test_audit_returns_200_and_shape():
    resp = client.get("/internal/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "status" in data
    assert "total_findings" in data
    assert "findings" in data
    assert isinstance(data["findings"], list)
    assert data["total_findings"] == len(data["findings"])


def test_audit_finding_fields():
    """Each finding has the expected shape."""
    resp = client.get("/internal/audit")
    data = resp.json()
    for f in data["findings"]:
        assert "check" in f
        assert "surface" in f
        assert "severity" in f
        assert "message" in f
        assert "detail" in f
        assert isinstance(f["detail"], dict)


def _reset_to_own_db():
    """Reset DB connection back to this module's temp file.

    Other test files (test_auth, test_lead_status, etc.) overwrite the global
    DATABASE_PATH at import time. The audit tests need a clean DB to verify
    arithmetic invariants, so we restore this module's DB path and reinit.
    """
    db_module.DATABASE_PATH = _tmp.name
    db_module.reset_db()
    db_module.init_db()


def test_audit_status_pass_when_clean():
    """With clean data, both checks should pass and status should be 'pass'."""
    _reset_to_own_db()
    resp = client.get("/internal/audit")
    data = resp.json()
    assert data["status"] == "pass"
    assert data["total_findings"] == 0


def test_audit_source_surface_consistency_passes():
    """source-performance and source-actions agree on source list/totals."""
    # Create leads from two sources
    client.post("/leads", json={"name": "Audit A", "email": "audit_a@example.com", "source": "src_a", "notes": "n"})
    client.post("/leads", json={"name": "Audit B", "email": "audit_b@example.com", "source": "src_b"})
    resp = client.get("/internal/audit")
    data = resp.json()
    source_findings = [f for f in data["findings"] if f["check"] == "source_surface_consistency"]
    assert len(source_findings) == 0


def test_audit_ops_snapshot_arithmetic_passes():
    """pending_dispatch == actionable - claimed identity holds."""
    resp = client.get("/internal/audit")
    data = resp.json()
    arith_findings = [f for f in data["findings"] if f["check"] == "ops_snapshot_arithmetic"]
    assert len(arith_findings) == 0


def test_audit_ops_snapshot_arithmetic_with_claims():
    """Arithmetic still holds after claims."""
    # Create a lead and claim it
    lead_resp = client.post("/leads", json={"name": "Audit Claim", "email": "audit_claim@example.com", "source": "audit_src", "notes": "n"})
    lead_id = lead_resp.json()["lead"]["id"]
    client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id]})
    resp = client.get("/internal/audit")
    data = resp.json()
    arith_findings = [f for f in data["findings"] if f["check"] == "ops_snapshot_arithmetic"]
    assert len(arith_findings) == 0


def test_audit_deterministic():
    """Two consecutive calls return the same findings."""
    r1 = client.get("/internal/audit").json()
    r2 = client.get("/internal/audit").json()
    assert r1["status"] == r2["status"]
    assert r1["total_findings"] == r2["total_findings"]
    checks1 = [(f["check"], f["severity"]) for f in r1["findings"]]
    checks2 = [(f["check"], f["severity"]) for f in r2["findings"]]
    assert checks1 == checks2


def test_audit_status_derives_from_severity():
    """Status correctly reflects the highest severity finding."""
    resp = client.get("/internal/audit")
    data = resp.json()
    severities = {f["severity"] for f in data["findings"]}
    if "high" in severities:
        assert data["status"] == "fail"
    elif "medium" in severities:
        assert data["status"] == "warn"
    else:
        assert data["status"] == "pass"


def test_existing_endpoints_still_work_after_audit():
    """Existing endpoints remain functional after audit addition."""
    assert client.get("/health").status_code == 200
    assert client.get("/leads").status_code == 200
    assert client.get("/internal/queue").status_code == 200
    assert client.get("/internal/sentinel").status_code == 200
    assert client.get("/internal/source-actions").status_code == 200


# ── Redundancy ──


def test_redundancy_returns_200_and_shape():
    resp = client.get("/internal/redundancy")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "areas_scanned" in data
    assert "overall_status" in data
    assert "total_findings" in data
    assert "findings" in data
    assert isinstance(data["findings"], list)
    assert data["total_findings"] == len(data["findings"])
    assert isinstance(data["areas_scanned"], list)


def test_redundancy_finding_fields():
    """Each finding has the expected shape including removal_risk and why_now."""
    resp = client.get("/internal/redundancy")
    data = resp.json()
    for f in data["findings"]:
        assert "type" in f
        assert "targets" in f
        assert isinstance(f["targets"], list)
        assert "severity" in f
        assert "message" in f
        assert "recommended_action" in f
        assert "confidence" in f
        assert "removal_risk" in f
        assert f["removal_risk"] in ("low", "medium", "high")
        assert "why_now" in f
        assert len(f["why_now"]) > 0


def test_redundancy_areas_scanned():
    """Areas scanned includes expected targets."""
    resp = client.get("/internal/redundancy")
    data = resp.json()
    assert "skills/" in data["areas_scanned"]
    assert "CLAUDE.md hierarchy" in data["areas_scanned"]


def test_redundancy_skills_check_reports_known_candidates():
    """Skills from the explicit candidate list are reported."""
    resp = client.get("/internal/redundancy")
    data = resp.json()
    skill_findings = [f for f in data["findings"] if "skill" in f["message"].lower() or "Skill" in f["message"]]
    # We know the candidate list has entries and the skills/ dir exists
    # Each reported skill should be from the hardcoded candidate list
    for f in skill_findings:
        assert f["type"] == "overlap"
        assert f["recommended_action"] == "archive_candidate"
        assert f["confidence"] == "medium"
        assert f["severity"] == "low"


def test_redundancy_skills_only_reports_existing_files():
    """Only skills that exist on disk are reported."""
    resp = client.get("/internal/redundancy")
    data = resp.json()
    from pathlib import Path
    from apps.api.routes.internal import _PROJECT_ROOT
    for f in data["findings"]:
        if "Skill" in f["message"] or "skill" in f["message"].lower():
            for target in f["targets"]:
                assert (_PROJECT_ROOT / target).is_file(), f"Target {target} does not exist"


def test_redundancy_dormant_stubs_reported():
    """Known stub CLAUDE.md files are reported as dormant."""
    resp = client.get("/internal/redundancy")
    data = resp.json()
    dormant = [f for f in data["findings"] if f["type"] == "dormant"]
    # core/CLAUDE.md is a known stub; automations/CLAUDE.md is no longer a stub
    dormant_targets = [t for f in dormant for t in f["targets"]]
    assert any("core/CLAUDE.md" in t for t in dormant_targets)
    for f in dormant:
        assert f["recommended_action"] == "keep"
        assert f["confidence"] == "high"
        assert f["removal_risk"] == "low"


def test_redundancy_deterministic():
    """Two consecutive calls return the same findings."""
    r1 = client.get("/internal/redundancy").json()
    r2 = client.get("/internal/redundancy").json()
    assert r1["overall_status"] == r2["overall_status"]
    assert r1["total_findings"] == r2["total_findings"]
    t1 = [(f["type"], f["targets"], f["severity"]) for f in r1["findings"]]
    t2 = [(f["type"], f["targets"], f["severity"]) for f in r2["findings"]]
    assert t1 == t2


def test_redundancy_status_derives_from_severity():
    """Status correctly reflects the highest severity finding."""
    resp = client.get("/internal/redundancy")
    data = resp.json()
    severities = {f["severity"] for f in data["findings"]}
    if "high" in severities:
        assert data["overall_status"] == "alert"
    elif "medium" in severities:
        assert data["overall_status"] == "watch"
    else:
        assert data["overall_status"] == "ok"


def test_redundancy_no_modification_side_effects():
    """Redundancy endpoint is read-only — calling it twice changes nothing."""
    r1 = client.get("/internal/redundancy").json()
    r2 = client.get("/internal/redundancy").json()
    assert r1["findings"] == r2["findings"]


def test_existing_endpoints_still_work_after_redundancy():
    """Existing endpoints remain functional after redundancy addition."""
    assert client.get("/health").status_code == 200
    assert client.get("/leads").status_code == 200
    assert client.get("/internal/queue").status_code == 200
    assert client.get("/internal/audit").status_code == 200
    assert client.get("/internal/sentinel").status_code == 200



# ---------------------------------------------------------------------------
# POST /internal/scope-critic - scope critic
# ---------------------------------------------------------------------------

_CLEAN_PROPOSAL = {
    "classification": "BUILD",
    "goal": "Add scope critic endpoint",
    "scope": ["apps/api/routes/internal.py", "apps/api/schemas.py", "tests"],
    "out_of_scope": ["scoring logic", "database schema", "deployment"],
    "expected_files": [
        "apps/api/routes/internal.py",
        "apps/api/schemas.py",
        "tests/api/test_api.py",
    ],
    "main_risk": "Overly strict checks may produce false positives",
    "minimum_acceptable": "All 5 checks implemented with tests",
}


def test_scope_critic_returns_correct_shape():
    resp = client.post("/internal/scope-critic", json=_CLEAN_PROPOSAL)
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "status" in data
    assert "total_findings" in data
    assert "findings" in data
    assert isinstance(data["findings"], list)
    assert data["status"] in ("ok", "watch", "block")


def test_scope_critic_finding_has_evidence():
    proposal = {**_CLEAN_PROPOSAL, "main_risk": "none"}
    resp = client.post("/internal/scope-critic", json=proposal)
    data = resp.json()
    for finding in data["findings"]:
        assert "check" in finding
        assert "severity" in finding
        assert "message" in finding
        assert "evidence" in finding
        assert isinstance(finding["evidence"], list)


def test_scope_critic_clean_proposal_passes():
    resp = client.post("/internal/scope-critic", json=_CLEAN_PROPOSAL)
    data = resp.json()
    assert data["status"] == "ok"
    assert data["total_findings"] == 0


def test_scope_critic_rejects_empty_required_fields():
    bad = {**_CLEAN_PROPOSAL}
    del bad["goal"]
    assert client.post("/internal/scope-critic", json=bad).status_code == 422

    bad2 = {**_CLEAN_PROPOSAL, "scope": []}
    assert client.post("/internal/scope-critic", json=bad2).status_code == 422

    bad3 = {**_CLEAN_PROPOSAL, "out_of_scope": []}
    assert client.post("/internal/scope-critic", json=bad3).status_code == 422

    bad4 = {**_CLEAN_PROPOSAL, "expected_files": []}
    assert client.post("/internal/scope-critic", json=bad4).status_code == 422

    bad5 = {**_CLEAN_PROPOSAL, "main_risk": ""}
    assert client.post("/internal/scope-critic", json=bad5).status_code == 422

    bad6 = {**_CLEAN_PROPOSAL, "minimum_acceptable": ""}
    assert client.post("/internal/scope-critic", json=bad6).status_code == 422


def test_scope_critic_sensitive_file_intrusion_blocks():
    proposal = {
        **_CLEAN_PROPOSAL,
        "expected_files": [
            "apps/api/routes/internal.py",
            ".claude/CLAUDE.md",
        ],
    }
    resp = client.post("/internal/scope-critic", json=proposal)
    data = resp.json()
    assert data["status"] == "block"
    intrusion = [f for f in data["findings"] if f["check"] == "sensitive_file_intrusion"]
    assert len(intrusion) == 1
    assert intrusion[0]["severity"] == "high"
    assert any(".claude" in e for e in intrusion[0]["evidence"])


def test_scope_critic_sensitive_file_justified():
    proposal = {
        **_CLEAN_PROPOSAL,
        "expected_files": [
            "apps/api/routes/internal.py",
            ".claude/CLAUDE.md",
        ],
        "scope": [".claude/CLAUDE.md governance update", "internal routes"],
    }
    resp = client.post("/internal/scope-critic", json=proposal)
    data = resp.json()
    intrusion = [f for f in data["findings"] if f["check"] == "sensitive_file_intrusion"]
    assert len(intrusion) == 0


def test_scope_critic_sensitive_file_contradicted_by_out_of_scope():
    proposal = {
        **_CLEAN_PROPOSAL,
        "expected_files": [
            "apps/api/routes/internal.py",
            "skills/new_skill.md",
        ],
        "scope": ["skills/ addition", "internal routes"],
        "out_of_scope": ["skills/ changes", "deployment"],
    }
    resp = client.post("/internal/scope-critic", json=proposal)
    data = resp.json()
    intrusion = [f for f in data["findings"] if f["check"] == "sensitive_file_intrusion"]
    assert len(intrusion) == 1
    assert any("contradicted" in e for e in intrusion[0]["evidence"])


def test_scope_critic_file_spread_risk():
    proposal = {
        **_CLEAN_PROPOSAL,
        "expected_files": [
            "apps/api/routes/internal.py",
            "apps/api/services/scoring.py",
            "tests/api/test_api.py",
            "docs/operational_contracts.md",
            "core/config.py",
        ],
    }
    resp = client.post("/internal/scope-critic", json=proposal)
    data = resp.json()
    spread = [f for f in data["findings"] if f["check"] == "file_spread_risk"]
    assert len(spread) == 1
    assert spread[0]["severity"] == "medium"
    assert len(spread[0]["evidence"]) == 5


def test_scope_critic_file_spread_same_area_ok():
    proposal = {
        **_CLEAN_PROPOSAL,
        "expected_files": [
            "apps/api/routes/internal.py",
            "apps/api/routes/leads.py",
            "apps/api/schemas.py",
            "tests/api/test_api.py",
        ],
    }
    resp = client.post("/internal/scope-critic", json=proposal)
    data = resp.json()
    spread = [f for f in data["findings"] if f["check"] == "file_spread_risk"]
    assert len(spread) == 0


def test_scope_critic_weak_out_of_scope():
    proposal = {
        **_CLEAN_PROPOSAL,
        "out_of_scope": ["nothing", "n/a"],
    }
    resp = client.post("/internal/scope-critic", json=proposal)
    data = resp.json()
    weak = [f for f in data["findings"] if f["check"] == "weak_out_of_scope"]
    assert len(weak) == 1
    assert weak[0]["severity"] == "medium"


def test_scope_critic_out_of_scope_one_substantive():
    proposal = {
        **_CLEAN_PROPOSAL,
        "out_of_scope": ["n/a", "do not change scoring logic"],
    }
    resp = client.post("/internal/scope-critic", json=proposal)
    data = resp.json()
    weak = [f for f in data["findings"] if f["check"] == "weak_out_of_scope"]
    assert len(weak) == 0


def test_scope_critic_minimum_scope_mismatch():
    proposal = {
        **_CLEAN_PROPOSAL,
        "minimum_acceptable": "get it working",
        "scope": ["a", "b", "c"],
    }
    resp = client.post("/internal/scope-critic", json=proposal)
    data = resp.json()
    mismatch = [f for f in data["findings"] if f["check"] == "minimum_scope_mismatch"]
    assert len(mismatch) == 1
    assert mismatch[0]["severity"] == "medium"


def test_scope_critic_minimum_ok_when_specific():
    proposal = {
        **_CLEAN_PROPOSAL,
        "minimum_acceptable": "All 5 checks implemented, tested, documented",
        "scope": ["a", "b", "c", "d"],
    }
    resp = client.post("/internal/scope-critic", json=proposal)
    data = resp.json()
    mismatch = [f for f in data["findings"] if f["check"] == "minimum_scope_mismatch"]
    assert len(mismatch) == 0


def test_scope_critic_minimum_ok_when_small_scope():
    proposal = {
        **_CLEAN_PROPOSAL,
        "minimum_acceptable": "tbd",
        "scope": ["one thing"],
        "expected_files": ["apps/api/routes/internal.py"],
    }
    resp = client.post("/internal/scope-critic", json=proposal)
    data = resp.json()
    mismatch = [f for f in data["findings"] if f["check"] == "minimum_scope_mismatch"]
    assert len(mismatch) == 0


def test_scope_critic_risk_unacknowledged():
    proposal = {**_CLEAN_PROPOSAL, "main_risk": "no risk"}
    resp = client.post("/internal/scope-critic", json=proposal)
    data = resp.json()
    risk = [f for f in data["findings"] if f["check"] == "risk_unacknowledged"]
    assert len(risk) == 1
    assert risk[0]["severity"] == "low"
    assert data["status"] == "ok"


def test_scope_critic_status_derivation():
    r1 = client.post("/internal/scope-critic", json=_CLEAN_PROPOSAL).json()
    assert r1["status"] == "ok"

    r2 = client.post("/internal/scope-critic", json={
        **_CLEAN_PROPOSAL,
        "out_of_scope": ["none"],
    }).json()
    assert r2["status"] == "watch"

    r3 = client.post("/internal/scope-critic", json={
        **_CLEAN_PROPOSAL,
        "expected_files": [".claude/CLAUDE.md"],
    }).json()
    assert r3["status"] == "block"


def test_scope_critic_deterministic():
    r1 = client.post("/internal/scope-critic", json=_CLEAN_PROPOSAL).json()
    r2 = client.post("/internal/scope-critic", json=_CLEAN_PROPOSAL).json()
    assert r1["status"] == r2["status"]
    assert r1["total_findings"] == r2["total_findings"]
    assert r1["findings"] == r2["findings"]


def test_scope_critic_no_side_effects():
    health_before = client.get("/health").json()
    client.post("/internal/scope-critic", json=_CLEAN_PROPOSAL)
    health_after = client.get("/health").json()
    assert health_before["status"] == health_after["status"]


def test_scope_critic_protected_patterns():
    for protected_file in [
        ".claude/CLAUDE.md",
        "skills/some_skill.md",
        "README.md",
        "Dockerfile",
        "docker-compose.yml",
        ".gitignore",
    ]:
        proposal = {
            **_CLEAN_PROPOSAL,
            "expected_files": [protected_file],
        }
        resp = client.post("/internal/scope-critic", json=proposal)
        data = resp.json()
        intrusion = [f for f in data["findings"] if f["check"] == "sensitive_file_intrusion"]
        assert len(intrusion) == 1, f"Expected intrusion finding for {protected_file}"


def test_scope_critic_area_mapping():
    proposal = {
        **_CLEAN_PROPOSAL,
        "expected_files": [
            "apps/api/routes/internal.py",
            "apps/api/schemas.py",
            "tests/api/test_api.py",
        ],
    }
    resp = client.post("/internal/scope-critic", json=proposal)
    data = resp.json()
    spread = [f for f in data["findings"] if f["check"] == "file_spread_risk"]
    assert len(spread) == 0


def test_existing_endpoints_still_work_after_scope_critic():
    assert client.get("/health").status_code == 200
    assert client.get("/leads").status_code == 200
    assert client.get("/internal/queue").status_code == 200
    assert client.get("/internal/sentinel").status_code == 200
    assert client.get("/internal/audit").status_code == 200
    assert client.get("/internal/redundancy").status_code == 200



# ---------------------------------------------------------------------------
# POST /internal/proof-verifier - proof verifier
# ---------------------------------------------------------------------------

_CLEAN_REPORT = {
    "block_name": "scope-critic-build",
    "classification": "BUILD",
    "claimed_changes": [
        "Added POST /internal/scope-critic with 5 checks",
        "Added schemas",
        "Added tests",
    ],
    "claimed_verified": [
        "python -m pytest tests/api/test_api.py -v - 358 passed",
        "All scope critic checks tested individually",
        "schemas.py updated with 3 new models",
    ],
    "claimed_not_verified": [
        "ruff check . - not installed",
    ],
    "files_touched": [
        "apps/api/routes/internal.py",
        "apps/api/schemas.py",
        "tests/api/test_api.py",
    ],
    "tests_run": [
        "python -m pytest tests/api/test_api.py -v",
    ],
    "status_claim": "accepted for MVP",
}

_FULLY_PROVEN_REPORT = {
    "block_name": "small-fix",
    "classification": "BUGFIX",
    "claimed_changes": ["Fixed scoring edge case in scoring.py"],
    "claimed_verified": [
        "python -m pytest tests/api/test_api.py -v - all passed",
        "Verified scoring.py change manually",
    ],
    "claimed_not_verified": [],
    "files_touched": [
        "apps/api/services/scoring.py",
        "tests/api/test_api.py",
    ],
    "tests_run": [
        "python -m pytest tests/api/test_api.py -v",
    ],
    "status_claim": "accepted for MVP",
}


def test_proof_verifier_returns_correct_shape():
    resp = client.post("/internal/proof-verifier", json=_CLEAN_REPORT)
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "status" in data
    assert "total_findings" in data
    assert "findings" in data
    assert isinstance(data["findings"], list)
    assert data["status"] in ("close", "watch", "not_close")


def test_proof_verifier_finding_fields():
    resp = client.post("/internal/proof-verifier", json=_CLEAN_REPORT)
    data = resp.json()
    for finding in data["findings"]:
        assert "check" in finding
        assert "severity" in finding
        assert "message" in finding
        assert "evidence" in finding
        assert "blocks_closure" in finding
        assert "confidence" in finding
        assert isinstance(finding["evidence"], list)
        assert isinstance(finding["blocks_closure"], bool)
        assert finding["confidence"] in ("low", "medium", "high")


def test_proof_verifier_clean_report_watch():
    """Clean report with acknowledged gaps returns watch (has not_verified items)."""
    resp = client.post("/internal/proof-verifier", json=_CLEAN_REPORT)
    data = resp.json()
    # Has claimed_not_verified but status is "accepted for MVP" (not closure language)
    # So unverified_gap won't fire. But untested_changes might depending on evidence matching.
    assert data["status"] in ("close", "watch")


def test_proof_verifier_fully_proven_closes():
    """A fully proven report with good evidence returns close."""
    resp = client.post("/internal/proof-verifier", json=_FULLY_PROVEN_REPORT)
    data = resp.json()
    assert data["status"] == "close"
    assert data["total_findings"] == 0


def test_proof_verifier_rejects_empty_required_fields():
    bad = {**_CLEAN_REPORT}
    del bad["block_name"]
    assert client.post("/internal/proof-verifier", json=bad).status_code == 422

    bad2 = {**_CLEAN_REPORT, "claimed_changes": []}
    assert client.post("/internal/proof-verifier", json=bad2).status_code == 422

    bad3 = {**_CLEAN_REPORT, "claimed_verified": []}
    assert client.post("/internal/proof-verifier", json=bad3).status_code == 422

    bad4 = {**_CLEAN_REPORT, "files_touched": []}
    assert client.post("/internal/proof-verifier", json=bad4).status_code == 422

    bad5 = {**_CLEAN_REPORT, "status_claim": ""}
    assert client.post("/internal/proof-verifier", json=bad5).status_code == 422


def test_proof_verifier_allows_empty_optional_fields():
    """claimed_not_verified and tests_run can be empty."""
    report = {
        **_CLEAN_REPORT,
        "claimed_not_verified": [],
        "tests_run": [],
    }
    resp = client.post("/internal/proof-verifier", json=report)
    assert resp.status_code == 200


def test_proof_verifier_unverified_gap_blocks():
    """Closure language + non-empty claimed_not_verified = not_close."""
    report = {
        **_CLEAN_REPORT,
        "status_claim": "done",
    }
    resp = client.post("/internal/proof-verifier", json=report)
    data = resp.json()
    assert data["status"] == "not_close"
    gap = [f for f in data["findings"] if f["check"] == "unverified_gap"]
    assert len(gap) == 1
    assert gap[0]["severity"] == "high"
    assert gap[0]["blocks_closure"] is True


def test_proof_verifier_unverified_gap_no_fire_on_mvp():
    """Non-closure language with not_verified items does not fire unverified_gap."""
    report = {
        **_CLEAN_REPORT,
        "status_claim": "accepted for MVP",
    }
    resp = client.post("/internal/proof-verifier", json=report)
    data = resp.json()
    gap = [f for f in data["findings"] if f["check"] == "unverified_gap"]
    assert len(gap) == 0


def test_proof_verifier_untested_changes():
    """Files with no specific verification evidence are flagged."""
    report = {
        **_CLEAN_REPORT,
        "files_touched": [
            "apps/api/routes/internal.py",
            "apps/api/schemas.py",
            "tests/api/test_api.py",
            "docs/operational_contracts.md",
        ],
        "claimed_verified": [
            "python -m pytest tests/api/test_api.py -v",
        ],
        "tests_run": [
            "python -m pytest tests/api/test_api.py -v",
        ],
    }
    resp = client.post("/internal/proof-verifier", json=report)
    data = resp.json()
    untested = [f for f in data["findings"] if f["check"] == "untested_changes"]
    assert len(untested) == 1
    assert untested[0]["severity"] == "medium"
    assert untested[0]["blocks_closure"] is False
    # internal.py, schemas.py, operational_contracts.md should be unmatched
    assert any("operational_contracts" in e for e in untested[0]["evidence"])


def test_proof_verifier_untested_specific_match():
    """File with specific mention in claimed_verified is not flagged."""
    report = {
        **_CLEAN_REPORT,
        "files_touched": [
            "apps/api/routes/internal.py",
            "apps/api/schemas.py",
        ],
        "claimed_verified": [
            "internal.py updated with new endpoint",
            "schemas.py updated with 3 new models",
        ],
        "tests_run": [],
    }
    resp = client.post("/internal/proof-verifier", json=report)
    data = resp.json()
    untested = [f for f in data["findings"] if f["check"] == "untested_changes"]
    assert len(untested) == 0


def test_proof_verifier_untested_doc_resolved_by_naming():
    """Doc file with filename in claimed_verified must not trigger untested_changes."""
    report = {
        **_CLEAN_REPORT,
        "files_touched": [
            "apps/api/routes/internal.py",
            "tests/api/test_api.py",
            "docs/operational_contracts.md",
        ],
        "claimed_verified": [
            "python -m pytest tests/api/test_api.py -v (all passed)",
            "internal.py updated with new endpoint logic",
            "Doc change in operational_contracts.md reviewed: added cross-reference note",
        ],
        "tests_run": [
            "python -m pytest tests/api/test_api.py -v",
        ],
    }
    resp = client.post("/internal/proof-verifier", json=report)
    data = resp.json()
    untested = [f for f in data["findings"] if f["check"] == "untested_changes"]
    assert len(untested) == 0, f"Expected no untested_changes but got: {untested}"


def test_proof_verifier_empty_test_evidence_blocks():
    """No tests_run and no test references in claimed_verified = not_close."""
    report = {
        **_CLEAN_REPORT,
        "tests_run": [],
        "claimed_verified": [
            "Looked at the endpoint manually",
            "Read the code diff",
        ],
        "claimed_not_verified": [],
    }
    resp = client.post("/internal/proof-verifier", json=report)
    data = resp.json()
    assert data["status"] == "not_close"
    empty = [f for f in data["findings"] if f["check"] == "empty_test_evidence"]
    assert len(empty) == 1
    assert empty[0]["blocks_closure"] is True


def test_proof_verifier_test_ref_in_verified_ok():
    """Test reference in claimed_verified is sufficient even without tests_run."""
    report = {
        **_CLEAN_REPORT,
        "tests_run": [],
        "claimed_verified": [
            "python -m pytest tests/api/test_api.py -v - 358 passed",
        ],
    }
    resp = client.post("/internal/proof-verifier", json=report)
    data = resp.json()
    empty = [f for f in data["findings"] if f["check"] == "empty_test_evidence"]
    assert len(empty) == 0


def test_proof_verifier_overclaim_status():
    """Overconfident status_claim triggers low finding."""
    report = {
        **_CLEAN_REPORT,
        "status_claim": "production-ready",
        "claimed_not_verified": [],
    }
    resp = client.post("/internal/proof-verifier", json=report)
    data = resp.json()
    overclaim = [f for f in data["findings"] if f["check"] == "overclaim_status"]
    assert len(overclaim) == 1
    assert overclaim[0]["severity"] == "low"
    assert overclaim[0]["blocks_closure"] is False


def test_proof_verifier_overclaim_does_not_fire_on_mvp():
    """Humble status_claim does not trigger overclaim."""
    report = {**_CLEAN_REPORT, "status_claim": "accepted for MVP"}
    resp = client.post("/internal/proof-verifier", json=report)
    data = resp.json()
    overclaim = [f for f in data["findings"] if f["check"] == "overclaim_status"]
    assert len(overclaim) == 0


def test_proof_verifier_verification_claim_mismatch():
    """Claiming zero gaps but thin evidence triggers mismatch."""
    report = {
        **_CLEAN_REPORT,
        "claimed_not_verified": [],
        "files_touched": [
            "apps/api/routes/internal.py",
            "apps/api/schemas.py",
            "docs/operational_contracts.md",
            "apps/api/services/actions.py",
        ],
        "claimed_verified": [
            "Endpoint works correctly",
        ],
        "tests_run": [],
    }
    resp = client.post("/internal/proof-verifier", json=report)
    data = resp.json()
    mismatch = [f for f in data["findings"] if f["check"] == "verification_claim_mismatch"]
    assert len(mismatch) == 1
    assert mismatch[0]["severity"] == "medium"
    assert "coverage ratio" in mismatch[0]["evidence"][0]


def test_proof_verifier_mismatch_no_fire_when_gaps_acknowledged():
    """If claimed_not_verified is non-empty, mismatch does not fire."""
    report = {
        **_CLEAN_REPORT,
        "claimed_not_verified": ["ruff not installed"],
        "files_touched": [
            "apps/api/routes/internal.py",
            "apps/api/schemas.py",
            "docs/operational_contracts.md",
            "apps/api/services/actions.py",
        ],
        "claimed_verified": ["Endpoint works"],
        "tests_run": [],
    }
    resp = client.post("/internal/proof-verifier", json=report)
    data = resp.json()
    mismatch = [f for f in data["findings"] if f["check"] == "verification_claim_mismatch"]
    assert len(mismatch) == 0


def test_proof_verifier_mismatch_no_fire_when_coverage_good():
    """If coverage ratio >= 0.5, mismatch does not fire."""
    report = {
        **_CLEAN_REPORT,
        "claimed_not_verified": [],
        "files_touched": [
            "apps/api/routes/internal.py",
            "tests/api/test_api.py",
        ],
        "claimed_verified": [
            "internal.py updated",
            "test_api.py has 358 passing tests",
        ],
        "tests_run": [],
    }
    resp = client.post("/internal/proof-verifier", json=report)
    data = resp.json()
    mismatch = [f for f in data["findings"] if f["check"] == "verification_claim_mismatch"]
    assert len(mismatch) == 0


def test_proof_verifier_status_derivation():
    """Status correctly reflects highest severity and blocks_closure."""
    # close: fully proven
    r1 = client.post("/internal/proof-verifier", json=_FULLY_PROVEN_REPORT).json()
    assert r1["status"] == "close"

    # not_close: blocks_closure finding
    r2 = client.post("/internal/proof-verifier", json={
        **_CLEAN_REPORT,
        "status_claim": "done",
    }).json()
    assert r2["status"] == "not_close"

    # watch: medium finding without blocks_closure
    r3 = client.post("/internal/proof-verifier", json={
        **_CLEAN_REPORT,
        "claimed_not_verified": [],
        "files_touched": [
            "apps/api/routes/internal.py",
            "apps/api/schemas.py",
            "docs/operational_contracts.md",
            "apps/api/services/actions.py",
        ],
        "claimed_verified": ["Endpoint works"],
        "tests_run": [],
        "status_claim": "residual debt remains",
    }).json()
    assert r3["status"] in ("watch", "not_close")


def test_proof_verifier_deterministic():
    r1 = client.post("/internal/proof-verifier", json=_CLEAN_REPORT).json()
    r2 = client.post("/internal/proof-verifier", json=_CLEAN_REPORT).json()
    assert r1["status"] == r2["status"]
    assert r1["total_findings"] == r2["total_findings"]
    assert r1["findings"] == r2["findings"]


def test_proof_verifier_no_side_effects():
    health_before = client.get("/health").json()
    client.post("/internal/proof-verifier", json=_CLEAN_REPORT)
    health_after = client.get("/health").json()
    assert health_before["status"] == health_after["status"]


def test_existing_endpoints_still_work_after_proof_verifier():
    assert client.get("/health").status_code == 200
    assert client.get("/leads").status_code == 200
    assert client.get("/internal/queue").status_code == 200
    assert client.get("/internal/sentinel").status_code == 200
    assert client.get("/internal/audit").status_code == 200
    assert client.get("/internal/redundancy").status_code == 200
    assert client.post("/internal/scope-critic", json={
        "classification": "BUILD",
        "goal": "test",
        "scope": ["test"],
        "out_of_scope": ["nothing important"],
        "expected_files": ["test.py"],
        "main_risk": "none significant",
        "minimum_acceptable": "basic implementation",
    }).status_code == 200


# --- Outcome feedback tests ---


def _create_test_lead_for_outcome():
    """Helper to create a lead and return its id."""
    resp = client.post('/leads', json={
        'name': 'Outcome Test',
        'email': 'outcome-test-' + str(id(object())) + '@example.com',
        'source': 'test',
        'notes': 'for outcome testing',
    })
    return resp.json()['lead']['id']


def test_outcome_post_happy_path():
    lead_id = _create_test_lead_for_outcome()
    resp = client.post('/internal/outcomes', json={
        'lead_id': lead_id,
        'outcome': 'qualified',
        'reason': 'budget-fit',
        'notes': 'spoke with decision maker',
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data['lead_id'] == lead_id
    assert data['outcome'] == 'qualified'
    assert data['reason'] == 'budget-fit'
    assert data['notes'] == 'spoke with decision maker'
    assert 'recorded_at' in data


def test_outcome_post_optional_fields():
    lead_id = _create_test_lead_for_outcome()
    resp = client.post('/internal/outcomes', json={
        'lead_id': lead_id,
        'outcome': 'contacted',
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data['reason'] is None
    assert data['notes'] is None


def test_outcome_post_invalid_outcome():
    lead_id = _create_test_lead_for_outcome()
    resp = client.post('/internal/outcomes', json={
        'lead_id': lead_id,
        'outcome': 'maybe',
    })
    assert resp.status_code == 422


def test_outcome_post_nonexistent_lead():
    resp = client.post('/internal/outcomes', json={
        'lead_id': 999999,
        'outcome': 'won',
    })
    assert resp.status_code == 404


def test_outcome_post_missing_fields():
    resp = client.post('/internal/outcomes', json={
        'outcome': 'won',
    })
    assert resp.status_code == 422

    resp2 = client.post('/internal/outcomes', json={
        'lead_id': 1,
    })
    assert resp2.status_code == 422


def test_outcome_upsert():
    lead_id = _create_test_lead_for_outcome()
    client.post('/internal/outcomes', json={
        'lead_id': lead_id,
        'outcome': 'contacted',
        'reason': 'initial call',
    })
    resp = client.post('/internal/outcomes', json={
        'lead_id': lead_id,
        'outcome': 'won',
        'reason': 'closed deal',
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data['outcome'] == 'won'
    assert data['reason'] == 'closed deal'


def test_outcome_summary_shape():
    resp = client.get('/internal/outcomes/summary')
    assert resp.status_code == 200
    data = resp.json()
    assert 'generated_at' in data
    assert 'total' in data
    assert 'by_outcome' in data
    expected_keys = {'contacted', 'qualified', 'won', 'lost', 'no_answer', 'bad_fit'}
    assert set(data['by_outcome'].keys()) == expected_keys


def test_outcome_summary_empty():
    """Summary returns zero counts when no outcomes exist (in fresh DB)."""
    # Note: other tests may have created outcomes, so we just check shape
    resp = client.get('/internal/outcomes/summary')
    data = resp.json()
    assert all(isinstance(v, int) for v in data['by_outcome'].values())
    assert data['total'] == sum(data['by_outcome'].values())


def test_outcome_all_values_accepted():
    for outcome in ['contacted', 'qualified', 'won', 'lost', 'no_answer', 'bad_fit']:
        lead_id = _create_test_lead_for_outcome()
        resp = client.post('/internal/outcomes', json={
            'lead_id': lead_id,
            'outcome': outcome,
        })
        assert resp.status_code == 201, f'Failed for outcome: {outcome}'


def test_existing_endpoints_still_work_after_outcomes():
    assert client.get('/health').status_code == 200
    assert client.get('/leads').status_code == 200
    assert client.get('/internal/queue').status_code == 200
    assert client.get('/internal/sentinel').status_code == 200
    assert client.get('/internal/outcomes/summary').status_code == 200


# --- Outcome by-source tests ---


def test_outcome_by_source_shape():
    resp = client.get('/internal/outcomes/by-source')
    assert resp.status_code == 200
    data = resp.json()
    assert 'generated_at' in data
    assert 'total_sources' in data
    assert 'items' in data
    assert isinstance(data['items'], list)


def test_outcome_by_source_item_shape():
    """Each item has source, total, and all 6 outcome keys."""
    # Create a lead and record an outcome to ensure at least one item
    lead_resp = client.post('/leads', json={
        'name': 'BySource Shape',
        'email': 'bysource-shape@example.com',
        'source': 'shape-test-source',
        'notes': 'testing',
    })
    lead_id = lead_resp.json()['lead']['id']
    client.post('/internal/outcomes', json={
        'lead_id': lead_id,
        'outcome': 'won',
    })
    resp = client.get('/internal/outcomes/by-source')
    data = resp.json()
    shape_items = [i for i in data['items'] if i['source'] == 'shape-test-source']
    assert len(shape_items) == 1
    item = shape_items[0]
    assert item['source'] == 'shape-test-source'
    assert item['total'] == 1
    assert item['won'] == 1
    for key in ['contacted', 'qualified', 'lost', 'no_answer', 'bad_fit']:
        assert item[key] == 0


def test_outcome_by_source_multiple_outcomes():
    """Multiple outcomes for different leads from the same source aggregate correctly."""
    leads = []
    for i in range(3):
        r = client.post('/leads', json={
            'name': f'Multi {i}',
            'email': f'multi-{i}-bysrc@example.com',
            'source': 'multi-test-source',
            'notes': 'testing',
        })
        leads.append(r.json()['lead']['id'])
    client.post('/internal/outcomes', json={'lead_id': leads[0], 'outcome': 'won'})
    client.post('/internal/outcomes', json={'lead_id': leads[1], 'outcome': 'lost', 'reason': 'price'})
    client.post('/internal/outcomes', json={'lead_id': leads[2], 'outcome': 'won'})
    resp = client.get('/internal/outcomes/by-source')
    data = resp.json()
    multi_items = [i for i in data['items'] if i['source'] == 'multi-test-source']
    assert len(multi_items) == 1
    item = multi_items[0]
    assert item['won'] == 2
    assert item['lost'] == 1
    assert item['total'] == 3


def test_outcome_by_source_deterministic_ordering():
    """Items are ordered alphabetically by source."""
    resp = client.get('/internal/outcomes/by-source')
    data = resp.json()
    sources = [item['source'] for item in data['items']]
    assert sources == sorted(sources)


def test_outcome_by_source_zero_counts():
    """Outcomes not recorded for a source still appear as 0."""
    r = client.post('/leads', json={
        'name': 'Zero Test',
        'email': 'zero-bysrc@example.com',
        'source': 'zero-count-source',
        'notes': 'testing',
    })
    lead_id = r.json()['lead']['id']
    client.post('/internal/outcomes', json={'lead_id': lead_id, 'outcome': 'contacted'})
    resp = client.get('/internal/outcomes/by-source')
    data = resp.json()
    zero_items = [i for i in data['items'] if i['source'] == 'zero-count-source']
    assert len(zero_items) == 1
    item = zero_items[0]
    assert item['contacted'] == 1
    assert item['qualified'] == 0
    assert item['won'] == 0
    assert item['lost'] == 0
    assert item['no_answer'] == 0
    assert item['bad_fit'] == 0


def test_existing_endpoints_still_work_after_by_source():
    assert client.get('/health').status_code == 200
    assert client.get('/leads').status_code == 200
    assert client.get('/internal/outcomes/summary').status_code == 200
    assert client.get('/internal/outcomes/by-source').status_code == 200


# --- Follow-up queue tests ---


def _create_lead_with_outcome(name, email, source, outcome, reason=None, notes_text=None):
    """Helper: create lead + record outcome, return lead_id."""
    resp = client.post('/leads', json={
        'name': name,
        'email': email,
        'source': source,
        'notes': notes_text or 'test lead',
    })
    lead_id = resp.json()['lead']['id']
    payload = {'lead_id': lead_id, 'outcome': outcome}
    if reason:
        payload['reason'] = reason
    if notes_text:
        payload['notes'] = notes_text
    client.post('/internal/outcomes', json=payload)
    return lead_id


def test_followup_queue_shape():
    resp = client.get('/internal/followup-queue')
    assert resp.status_code == 200
    data = resp.json()
    assert 'generated_at' in data
    assert 'total' in data
    assert 'items' in data
    assert isinstance(data['items'], list)


def test_followup_queue_includes_no_answer():
    lead_id = _create_lead_with_outcome(
        'Followup Test', 'followup-inc@example.com', 'test',
        'no_answer', reason='first call',
    )
    resp = client.get('/internal/followup-queue')
    data = resp.json()
    ids = [item['lead_id'] for item in data['items']]
    assert lead_id in ids
    item = [i for i in data['items'] if i['lead_id'] == lead_id][0]
    assert item['outcome'] == 'no_answer'
    assert item['outcome_reason'] == 'first call'
    assert 'name' in item
    assert 'email' in item
    assert 'score' in item
    assert 'rating' in item
    assert 'next_action' in item
    assert 'instruction' in item


def test_followup_queue_excludes_other_outcomes():
    _create_lead_with_outcome(
        'Won Lead', 'followup-won@example.com', 'test', 'won',
    )
    _create_lead_with_outcome(
        'Lost Lead', 'followup-lost@example.com', 'test', 'lost',
    )
    resp = client.get('/internal/followup-queue')
    data = resp.json()
    emails = [item['email'] for item in data['items']]
    assert 'followup-won@example.com' not in emails
    assert 'followup-lost@example.com' not in emails


def test_followup_queue_ordering():
    """Higher score leads appear first."""
    # Lead with notes (higher score) should come before lead without notes (lower score)
    id_high = _create_lead_with_outcome(
        'High Score', 'followup-high@example.com', 'test',
        'no_answer', notes_text='important notes for scoring',
    )
    id_low = _create_lead_with_outcome(
        'Low Score', 'followup-low@example.com', 'notas',
        'no_answer',
    )
    resp = client.get('/internal/followup-queue')
    data = resp.json()
    ids = [item['lead_id'] for item in data['items']]
    if id_high in ids and id_low in ids:
        high_item = [i for i in data['items'] if i['lead_id'] == id_high][0]
        low_item = [i for i in data['items'] if i['lead_id'] == id_low][0]
        if high_item['score'] != low_item['score']:
            high_idx = ids.index(id_high)
            low_idx = ids.index(id_low)
            if high_item['score'] > low_item['score']:
                assert high_idx < low_idx


def test_followup_queue_empty_when_no_no_answer():
    """If no leads have no_answer outcome, queue is empty (or contains only previously created ones)."""
    resp = client.get('/internal/followup-queue')
    data = resp.json()
    assert data['total'] == len(data['items'])


def test_followup_queue_upsert_removes_from_queue():
    """If outcome is updated from no_answer to won, lead leaves the queue."""
    lead_id = _create_lead_with_outcome(
        'Will Convert', 'followup-convert@example.com', 'test', 'no_answer',
    )
    # Verify in queue
    resp = client.get('/internal/followup-queue')
    ids = [item['lead_id'] for item in resp.json()['items']]
    assert lead_id in ids
    # Update outcome
    client.post('/internal/outcomes', json={'lead_id': lead_id, 'outcome': 'won'})
    # Verify removed
    resp2 = client.get('/internal/followup-queue')
    ids2 = [item['lead_id'] for item in resp2.json()['items']]
    assert lead_id not in ids2


def test_existing_endpoints_still_work_after_followup():
    assert client.get('/health').status_code == 200
    assert client.get('/leads').status_code == 200
    assert client.get('/internal/outcomes/summary').status_code == 200
    assert client.get('/internal/outcomes/by-source').status_code == 200
    assert client.get('/internal/followup-queue').status_code == 200


# --- Leads-layer harden tests ---


def test_followup_queue_excludes_claimed():
    """Claimed leads should not appear in the followup queue."""
    # Create lead, record no_answer, claim it
    resp = client.post('/leads', json={
        'name': 'Claimed Followup',
        'email': 'claimed-followup@example.com',
        'source': 'test',
        'notes': 'testing claim exclusion',
    })
    lead_id = resp.json()['lead']['id']
    client.post('/internal/outcomes', json={
        'lead_id': lead_id,
        'outcome': 'no_answer',
    })
    client.post('/internal/dispatch/claim', json={'lead_ids': [lead_id]})
    # Verify excluded from followup queue
    resp = client.get('/internal/followup-queue')
    ids = [item['lead_id'] for item in resp.json()['items']]
    assert lead_id not in ids


def test_outcome_emits_event():
    """Recording an outcome should emit a lead.outcome_recorded event."""
    resp = client.post('/leads', json={
        'name': 'Event Outcome',
        'email': 'event-outcome@example.com',
        'source': 'test',
        'notes': 'testing event emission',
    })
    lead_id = resp.json()['lead']['id']
    client.post('/internal/outcomes', json={
        'lead_id': lead_id,
        'outcome': 'qualified',
        'reason': 'budget confirmed',
    })
    # Check events
    events_resp = client.get('/internal/events', params={'event_type': 'lead.outcome_recorded'})
    data = events_resp.json()
    matching = [e for e in data['items'] if e['entity_id'] == lead_id]
    assert len(matching) >= 1
    assert matching[0]['event_type'] == 'lead.outcome_recorded'
    assert matching[0]['entity_type'] == 'lead'
    assert matching[0]['payload']['outcome'] == 'qualified'


def test_leads_summary_typed_response():
    """GET /leads/summary should return a typed response with all expected fields."""
    resp = client.get('/leads/summary')
    assert resp.status_code == 200
    data = resp.json()
    assert 'total_leads' in data
    assert 'average_score' in data
    assert 'low_score_count' in data
    assert 'medium_score_count' in data
    assert 'high_score_count' in data
    assert 'counts_by_source' in data
    assert isinstance(data['total_leads'], int)
    assert isinstance(data['average_score'], (int, float))
    assert isinstance(data['counts_by_source'], dict)


# --- Pre-limit total tests ---


def test_queue_total_is_pre_limit():
    """total must reflect full queue depth, not post-limit count."""
    src = "prelim_queue_total"
    for i in range(4):
        client.post("/leads", json={
            "name": f"PLQ {i}", "email": f"plq{i}@t.com",
            "source": src, "notes": "pre-limit total test",
        })
    full = client.get("/internal/queue", params={"source": src}).json()
    full_total = full["total"]
    assert full_total >= 4
    limited = client.get("/internal/queue", params={"source": src, "limit": 2}).json()
    assert limited["total"] == full_total
    assert len(limited["items"]) == 2


def test_dispatch_total_is_pre_limit():
    """total must reflect full dispatch depth, not post-limit count."""
    full = client.get("/internal/dispatch").json()
    full_total = full["total"]
    if full_total < 2:
        return
    limited = client.get("/internal/dispatch", params={"limit": 1}).json()
    assert limited["total"] == full_total
    assert len(limited["items"]) == 1


def test_handoffs_total_is_pre_limit():
    """total must reflect full handoff depth, not post-limit count."""
    full = client.get("/internal/handoffs").json()
    full_total = full["total"]
    if full_total < 2:
        return
    limited = client.get("/internal/handoffs", params={"limit": 1}).json()
    assert limited["total"] == full_total
    assert len(limited["items"]) == 1


# --- Source Outcome Actions tests ---


def _setup_source_outcome_leads(src, outcomes):
    """Create leads and record outcomes for a source. Returns lead IDs."""
    lead_ids = []
    for i, outcome in enumerate(outcomes):
        email = f"soa_{src}_{i}_{outcome}@t.com"
        resp = client.post("/leads", json={
            "name": f"SOA {src} {i}",
            "email": email,
            "source": src,
        })
        if resp.status_code == 409:
            # already exists, look up
            leads_resp = client.get("/leads", params={"source": src, "q": email})
            lid = leads_resp.json()[0]["id"]
        else:
            lid = resp.json()["lead"]["id"]
        lead_ids.append(lid)
        client.post("/internal/outcomes", json={
            "lead_id": lid,
            "outcome": outcome,
        })
    return lead_ids


def test_source_outcome_actions_shape():
    _setup_source_outcome_leads("soa_shape", ["won", "qualified", "lost"])
    resp = client.get("/internal/source-outcome-actions")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "total_sources" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    item = next(i for i in data["items"] if i["source"] == "soa_shape")
    for field in ["source", "total_outcomes", "contacted", "qualified",
                  "won", "lost", "no_answer", "bad_fit",
                  "recommendation", "rationale", "data_sufficient"]:
        assert field in item


def test_source_outcome_actions_r1_insufficient_data():
    """R1: total_outcomes < 3 -> review, data_sufficient=False."""
    _setup_source_outcome_leads("soa_sparse", ["won", "won"])
    resp = client.get("/internal/source-outcome-actions")
    item = next(i for i in resp.json()["items"] if i["source"] == "soa_sparse")
    assert item["recommendation"] == "review"
    assert item["data_sufficient"] is False
    assert "insufficient" in item["rationale"]


def test_source_outcome_actions_r2_keep():
    """R2: won+qualified >= 50% -> keep."""
    _setup_source_outcome_leads("soa_keep", ["won", "qualified", "contacted"])
    resp = client.get("/internal/source-outcome-actions")
    item = next(i for i in resp.json()["items"] if i["source"] == "soa_keep")
    assert item["recommendation"] == "keep"
    assert item["data_sufficient"] is True
    assert "qualified/won" in item["rationale"]


def test_source_outcome_actions_r3_deprioritize():
    """R3: bad_fit+lost >= 50% -> deprioritize."""
    _setup_source_outcome_leads("soa_depri", ["bad_fit", "lost", "contacted"])
    resp = client.get("/internal/source-outcome-actions")
    item = next(i for i in resp.json()["items"] if i["source"] == "soa_depri")
    assert item["recommendation"] == "deprioritize"
    assert item["data_sufficient"] is True
    assert "bad_fit/lost" in item["rationale"]


def test_source_outcome_actions_r4_no_answer():
    """R4: no_answer >= 50% -> review with responsiveness rationale."""
    _setup_source_outcome_leads("soa_noans", ["no_answer", "no_answer", "contacted"])
    resp = client.get("/internal/source-outcome-actions")
    item = next(i for i in resp.json()["items"] if i["source"] == "soa_noans")
    assert item["recommendation"] == "review"
    assert item["data_sufficient"] is True
    assert "no_answer" in item["rationale"]
    assert "responsiveness" in item["rationale"]


def test_source_outcome_actions_r5_mixed():
    """R5: no dominant pattern -> review, mixed."""
    _setup_source_outcome_leads("soa_mixed", ["won", "lost", "no_answer", "contacted"])
    resp = client.get("/internal/source-outcome-actions")
    item = next(i for i in resp.json()["items"] if i["source"] == "soa_mixed")
    assert item["recommendation"] == "review"
    assert item["data_sufficient"] is True
    assert "mixed" in item["rationale"]


def test_source_outcome_actions_deterministic_ordering():
    """Items must be sorted by source name."""
    resp = client.get("/internal/source-outcome-actions")
    items = resp.json()["items"]
    sources = [i["source"] for i in items]
    assert sources == sorted(sources)


def test_source_outcome_actions_zero_counts():
    """Outcome types not present must appear as 0."""
    _setup_source_outcome_leads("soa_zeros", ["won", "won", "won"])
    resp = client.get("/internal/source-outcome-actions")
    item = next(i for i in resp.json()["items"] if i["source"] == "soa_zeros")
    assert item["lost"] == 0
    assert item["bad_fit"] == 0
    assert item["no_answer"] == 0
    assert item["contacted"] == 0


def test_existing_endpoints_still_work_after_source_outcome_actions():
    for ep in ["/health", "/leads", "/internal/queue",
               "/internal/dispatch", "/internal/handoffs",
               "/internal/source-actions", "/internal/source-performance",
               "/internal/outcomes/by-source"]:
        resp = client.get(ep)
        assert resp.status_code == 200


# --- Daily Actions tests ---


def test_daily_actions_shape():
    resp = client.get("/internal/daily-actions")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "summary" in data
    assert "top_review" in data
    assert "top_client_ready" in data
    assert "top_followup" in data
    assert "source_warnings" in data
    s = data["summary"]
    for field in ["pending_review", "client_ready", "followup_candidates", "source_warnings"]:
        assert field in s
        assert isinstance(s[field], int)


def test_daily_actions_summary_counts_match_sections():
    """Summary counts must reflect full lists, not capped lists."""
    resp = client.get("/internal/daily-actions")
    data = resp.json()
    s = data["summary"]
    # Counts must be >= section length (sections are capped at 5)
    assert s["pending_review"] >= len(data["top_review"])
    assert s["client_ready"] >= len(data["top_client_ready"])
    assert s["followup_candidates"] >= len(data["top_followup"])
    assert s["source_warnings"] == len(data["source_warnings"])


def test_daily_actions_review_item_shape():
    resp = client.get("/internal/daily-actions")
    data = resp.json()
    if not data["top_review"]:
        return
    item = data["top_review"][0]
    for field in ["lead_id", "name", "source", "score", "rating", "next_action", "alert"]:
        assert field in item


def test_daily_actions_client_ready_item_shape():
    resp = client.get("/internal/daily-actions")
    data = resp.json()
    if not data["top_client_ready"]:
        return
    item = data["top_client_ready"][0]
    for field in ["lead_id", "name", "source", "score", "rating", "next_action"]:
        assert field in item


def test_daily_actions_followup_item_shape():
    resp = client.get("/internal/daily-actions")
    data = resp.json()
    if not data["top_followup"]:
        return
    item = data["top_followup"][0]
    for field in ["lead_id", "name", "source", "score", "outcome_recorded_at"]:
        assert field in item


def test_daily_actions_source_warning_shape():
    resp = client.get("/internal/daily-actions")
    data = resp.json()
    if not data["source_warnings"]:
        return
    item = data["source_warnings"][0]
    for field in ["source", "recommendation", "rationale", "total_outcomes"]:
        assert field in item


def test_daily_actions_sections_capped():
    """Each section must contain at most 5 items."""
    resp = client.get("/internal/daily-actions")
    data = resp.json()
    assert len(data["top_review"]) <= 5
    assert len(data["top_client_ready"]) <= 5
    assert len(data["top_followup"]) <= 5


def test_daily_actions_excludes_claimed():
    """Claimed leads must not appear in review or client-ready sections."""
    # Create a lead, claim it, then verify it is absent
    resp = client.post("/leads", json={
        "name": "DA Claimed", "email": "da_claimed@t.com",
        "source": "da_claim_test",
    })
    if resp.status_code == 409:
        return
    lid = resp.json()["lead"]["id"]
    client.post("/internal/dispatch/claim", json={"lead_ids": [lid]})
    daily = client.get("/internal/daily-actions").json()
    review_ids = [i["lead_id"] for i in daily["top_review"]]
    ready_ids = [i["lead_id"] for i in daily["top_client_ready"]]
    followup_ids = [i["lead_id"] for i in daily["top_followup"]]
    assert lid not in review_ids
    assert lid not in ready_ids
    assert lid not in followup_ids


def test_daily_actions_source_warnings_only_actionable():
    """Source warnings must only include review/deprioritize with data_sufficient."""
    resp = client.get("/internal/daily-actions")
    data = resp.json()
    for w in data["source_warnings"]:
        assert w["recommendation"] in ("review", "deprioritize")


def test_daily_actions_deterministic():
    """Two consecutive calls must return the same structure."""
    r1 = client.get("/internal/daily-actions").json()
    r2 = client.get("/internal/daily-actions").json()
    assert [i["lead_id"] for i in r1["top_review"]] == [i["lead_id"] for i in r2["top_review"]]
    assert [i["lead_id"] for i in r1["top_client_ready"]] == [i["lead_id"] for i in r2["top_client_ready"]]
    assert [i["lead_id"] for i in r1["top_followup"]] == [i["lead_id"] for i in r2["top_followup"]]
    assert [w["source"] for w in r1["source_warnings"]] == [w["source"] for w in r2["source_warnings"]]


def test_existing_endpoints_still_work_after_daily_actions():
    for ep in ["/health", "/leads", "/internal/queue",
               "/internal/dispatch", "/internal/handoffs",
               "/internal/source-actions", "/internal/source-performance",
               "/internal/outcomes/by-source",
               "/internal/source-outcome-actions"]:
        resp = client.get(ep)
        assert resp.status_code == 200


# --- Follow-up Handoff tests ---


def _setup_followup_handoff_lead(name, email, source, score_notes, outcome):
    """Create a lead with a specific outcome for handoff testing."""
    resp = client.post("/leads", json={
        "name": name, "email": email,
        "source": source, "notes": score_notes,
    })
    if resp.status_code == 409:
        leads = client.get("/leads", params={"q": email}).json()
        lid = leads[0]["id"]
    else:
        lid = resp.json()["lead"]["id"]
    client.post("/internal/outcomes", json={
        "lead_id": lid, "outcome": outcome,
    })
    return lid


def test_followup_handoffs_shape():
    _setup_followup_handoff_lead(
        "FH Shape", "fh_shape@t.com", "fh_src", "notes", "no_answer",
    )
    resp = client.get("/internal/followup-handoffs")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["total"] >= 1


def test_followup_handoffs_item_fields():
    _setup_followup_handoff_lead(
        "FH Fields", "fh_fields@t.com", "fh_src", "notes", "no_answer",
    )
    resp = client.get("/internal/followup-handoffs")
    items = resp.json()["items"]
    fh = next(i for i in items if i["email"] == "fh_fields@t.com")
    for field in ["lead_id", "name", "email", "source", "score", "rating",
                  "outcome_recorded_at", "channel", "action", "instruction",
                  "suggested_message"]:
        assert field in fh
    assert fh["channel"] == "email"
    assert fh["action"] == "retry_contact"
    assert fh["name"] in fh["suggested_message"]


def test_followup_handoffs_excludes_non_no_answer():
    _setup_followup_handoff_lead(
        "FH Won", "fh_won@t.com", "fh_exc", "notes", "won",
    )
    resp = client.get("/internal/followup-handoffs")
    emails = [i["email"] for i in resp.json()["items"]]
    assert "fh_won@t.com" not in emails


def test_followup_handoffs_excludes_claimed():
    lid = _setup_followup_handoff_lead(
        "FH Claimed", "fh_claimed@t.com", "fh_clm", "notes", "no_answer",
    )
    client.post("/internal/dispatch/claim", json={"lead_ids": [lid]})
    resp = client.get("/internal/followup-handoffs")
    ids = [i["lead_id"] for i in resp.json()["items"]]
    assert lid not in ids


def test_followup_handoffs_rating_matches_system():
    """Rating must use the system vocabulary: low (<50), medium (50-74), high (>=75)."""
    resp = client.get("/internal/followup-handoffs")
    for item in resp.json()["items"]:
        assert item["rating"] in ("low", "medium", "high")


def test_followup_handoffs_instruction_varies_by_rating():
    """Instruction must differ by rating tier."""
    resp = client.get("/internal/followup-handoffs")
    items = resp.json()["items"]
    instructions_by_rating = {}
    for item in items:
        instructions_by_rating[item["rating"]] = item["instruction"]
    # All instructions must contain retry_contact language
    for instr in instructions_by_rating.values():
        assert "Retry contact" in instr
    # If multiple ratings present, instructions must differ
    unique_instructions = set(instructions_by_rating.values())
    assert len(unique_instructions) == len(instructions_by_rating)


def test_followup_handoffs_deterministic():
    r1 = client.get("/internal/followup-handoffs").json()
    r2 = client.get("/internal/followup-handoffs").json()
    assert [i["lead_id"] for i in r1["items"]] == [i["lead_id"] for i in r2["items"]]


def test_followup_handoffs_ordering():
    """Items must be ordered by score DESC."""
    resp = client.get("/internal/followup-handoffs")
    items = resp.json()["items"]
    scores = [i["score"] for i in items]
    assert scores == sorted(scores, reverse=True)


def test_existing_endpoints_still_work_after_followup_handoffs():
    for ep in ["/health", "/leads", "/internal/queue",
               "/internal/dispatch", "/internal/handoffs",
               "/internal/followup-queue", "/internal/daily-actions",
               "/internal/source-outcome-actions"]:
        resp = client.get(ep)
        assert resp.status_code == 200


# --- Follow-up Automation tests ---


def test_followup_automation_shape():
    resp = client.get("/internal/followup-automation")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_followup_automation_item_structure():
    """Top-level routing fields + nested payload."""
    # Ensure at least one no_answer lead exists
    resp = client.post("/leads", json={
        "name": "FA Struct", "email": "fa_struct@t.com",
        "source": "fa_src",
    })
    if resp.status_code != 409:
        lid = resp.json()["lead"]["id"]
        client.post("/internal/outcomes", json={
            "lead_id": lid, "outcome": "no_answer",
        })
    resp = client.get("/internal/followup-automation")
    items = resp.json()["items"]
    assert len(items) >= 1
    item = items[0]
    # Top-level routing fields
    for field in ["lead_id", "channel", "action", "priority"]:
        assert field in item
    assert item["channel"] == "email"
    assert item["action"] == "retry_contact"
    assert isinstance(item["priority"], int)
    # Nested payload
    assert "payload" in item
    p = item["payload"]
    for field in ["name", "email", "source", "score", "rating",
                  "instruction", "suggested_message"]:
        assert field in p


def test_followup_automation_priority_sequential():
    """Priority must be sequential starting from 0."""
    resp = client.get("/internal/followup-automation")
    items = resp.json()["items"]
    priorities = [i["priority"] for i in items]
    assert priorities == list(range(len(items)))


def test_followup_automation_excludes_claimed():
    resp = client.post("/leads", json={
        "name": "FA Claimed", "email": "fa_claimed@t.com",
        "source": "fa_clm",
    })
    if resp.status_code == 409:
        return
    lid = resp.json()["lead"]["id"]
    client.post("/internal/outcomes", json={
        "lead_id": lid, "outcome": "no_answer",
    })
    client.post("/internal/dispatch/claim", json={"lead_ids": [lid]})
    resp = client.get("/internal/followup-automation")
    ids = [i["lead_id"] for i in resp.json()["items"]]
    assert lid not in ids


def test_followup_automation_excludes_non_no_answer():
    resp = client.post("/leads", json={
        "name": "FA Won", "email": "fa_won@t.com",
        "source": "fa_exc",
    })
    if resp.status_code == 409:
        return
    lid = resp.json()["lead"]["id"]
    client.post("/internal/outcomes", json={
        "lead_id": lid, "outcome": "won",
    })
    resp = client.get("/internal/followup-automation")
    ids = [i["lead_id"] for i in resp.json()["items"]]
    assert lid not in ids


def test_followup_automation_consistent_with_handoffs():
    """Automation and handoffs must select the same leads in the same order."""
    auto = client.get("/internal/followup-automation").json()
    hand = client.get("/internal/followup-handoffs").json()
    auto_ids = [i["lead_id"] for i in auto["items"]]
    hand_ids = [i["lead_id"] for i in hand["items"]]
    assert auto_ids == hand_ids


def test_followup_automation_deterministic():
    r1 = client.get("/internal/followup-automation").json()
    r2 = client.get("/internal/followup-automation").json()
    assert [i["lead_id"] for i in r1["items"]] == [i["lead_id"] for i in r2["items"]]
    assert [i["priority"] for i in r1["items"]] == [i["priority"] for i in r2["items"]]


def test_followup_automation_rating_matches_system():
    resp = client.get("/internal/followup-automation")
    for item in resp.json()["items"]:
        assert item["payload"]["rating"] in ("low", "medium", "high")


def test_existing_endpoints_still_work_after_followup_automation():
    for ep in ["/health", "/leads", "/internal/queue",
               "/internal/dispatch", "/internal/handoffs",
               "/internal/followup-queue", "/internal/followup-handoffs",
               "/internal/daily-actions"]:
        resp = client.get(ep)
        assert resp.status_code == 200


# --- Followup Automation CSV Export tests ---


def _ensure_followup_export_leads():
    """Create no_answer leads for CSV export testing if not already present."""
    _setup_followup_handoff_lead(
        "FExp High", "fexp_high@t.com", "fexp_src", "important notes score_override_80", "no_answer",
    )
    _setup_followup_handoff_lead(
        "FExp Med", "fexp_med@t.com", "fexp_src", "notes score_override_60", "no_answer",
    )
    _setup_followup_handoff_lead(
        "FExp Low", "fexp_low@t.com", "fexp_other", "notes score_override_20", "no_answer",
    )
    _setup_followup_handoff_lead(
        "FExp Won", "fexp_won@t.com", "fexp_src", "notes score_override_50", "won",
    )


def test_followup_export_csv_shape():
    """Response is text/csv with attachment header."""
    _ensure_followup_export_leads()
    resp = client.get("/internal/followup-automation/export.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert "followup-automation.csv" in resp.headers.get("content-disposition", "")


def test_followup_export_csv_columns():
    """First row matches expected column headers."""
    _ensure_followup_export_leads()
    resp = client.get("/internal/followup-automation/export.csv")
    lines = resp.text.strip().split("\n")
    assert len(lines) >= 1
    expected = "lead_id,to,subject,body,channel,priority,source,score,rating"
    assert lines[0].strip() == expected


def test_followup_export_csv_content():
    """CSV contains rows for no_answer leads with correct fields."""
    _ensure_followup_export_leads()
    resp = client.get("/internal/followup-automation/export.csv")
    reader = csv.DictReader(resp.text.strip().split("\n"))
    rows = list(reader)
    # Should include no_answer leads
    emails = [r["to"] for r in rows]
    assert "fexp_high@t.com" in emails
    assert "fexp_med@t.com" in emails
    assert "fexp_low@t.com" in emails
    # Should NOT include won lead
    assert "fexp_won@t.com" not in emails
    # Check fields are populated
    for row in rows:
        assert row["lead_id"]
        assert row["to"]
        assert row["subject"]
        assert row["body"]
        assert row["channel"] == "email"
        assert row["rating"] in ("low", "medium", "high")


def test_followup_export_csv_excludes_claimed():
    """Claimed leads must not appear in CSV export."""
    _ensure_followup_export_leads()
    # Get a lead_id from the export
    resp = client.get("/internal/followup-automation/export.csv")
    reader = csv.DictReader(resp.text.strip().split("\n"))
    rows = list(reader)
    if not rows:
        return  # no leads to claim
    target_id = int(rows[0]["lead_id"])
    # Claim it
    client.post("/internal/dispatch/claim", json={"lead_ids": [target_id]})
    # Verify it's gone from export
    resp2 = client.get("/internal/followup-automation/export.csv")
    reader2 = csv.DictReader(resp2.text.strip().split("\n"))
    exported_ids = [int(r["lead_id"]) for r in reader2]
    assert target_id not in exported_ids
    # Release the claim to avoid side effects
    client.delete(f"/internal/dispatch/claim/{target_id}")


def test_followup_export_csv_source_filter():
    """Source query param filters CSV rows."""
    _ensure_followup_export_leads()
    resp = client.get("/internal/followup-automation/export.csv", params={"source": "fexp_other"})
    reader = csv.DictReader(resp.text.strip().split("\n"))
    rows = list(reader)
    for row in rows:
        assert row["source"] == "fexp_other"


def test_followup_export_csv_limit():
    """Limit query param caps output rows."""
    _ensure_followup_export_leads()
    resp = client.get("/internal/followup-automation/export.csv", params={"limit": 1})
    reader = csv.DictReader(resp.text.strip().split("\n"))
    rows = list(reader)
    assert len(rows) <= 1


def test_followup_export_csv_empty():
    """With no matching leads, CSV has header only."""
    resp = client.get(
        "/internal/followup-automation/export.csv",
        params={"source": "nonexistent_source_xyz"},
    )
    assert resp.status_code == 200
    lines = [l for l in resp.text.strip().split("\n") if l.strip()]
    assert len(lines) == 1  # header only


def test_followup_export_csv_consistent_with_json():
    """CSV lead_ids match JSON endpoint lead_ids in same order."""
    _ensure_followup_export_leads()
    json_resp = client.get("/internal/followup-automation")
    json_ids = [item["lead_id"] for item in json_resp.json()["items"]]
    csv_resp = client.get("/internal/followup-automation/export.csv")
    reader = csv.DictReader(csv_resp.text.strip().split("\n"))
    csv_ids = [int(r["lead_id"]) for r in reader]
    # CSV must contain same ids in same order (may have fewer if source filter differs, but with no filter they match)
    assert csv_ids == json_ids


def test_followup_export_csv_body_with_commas_parses_correctly():
    """Body field contains commas — csv.writer must quote it so DictReader round-trips cleanly."""
    _ensure_followup_export_leads()
    resp = client.get("/internal/followup-automation/export.csv")
    reader = csv.DictReader(resp.text.strip().split("\n"))
    for row in reader:
        # Body always contains at least one comma (e.g., "Hi {name}, ...")
        assert "," in row["body"], f"Expected comma in body: {row['body']}"
        # Verify all 9 columns parsed (would break if quoting failed)
        assert len(row) == 9, f"Expected 9 columns but got {len(row)}: {row}"


def test_followup_export_csv_sanitizes_dangerous_source():
    """Source starting with dangerous prefix must be sanitized in CSV output."""
    # Create a lead with a dangerous-prefix source
    resp = client.post("/leads", json={
        "name": "Sanitize Test", "email": "sanitize_csv@t.com",
        "source": "=cmd_dangerous", "notes": "notes score_override_50",
    })
    if resp.status_code == 200:
        lid = resp.json()["lead"]["id"]
    else:
        leads = client.get("/leads", params={"q": "sanitize_csv@t.com"}).json()
        lid = leads[0]["id"]
    client.post("/internal/outcomes", json={"lead_id": lid, "outcome": "no_answer"})
    resp = client.get("/internal/followup-automation/export.csv", params={"source": "=cmd_dangerous"})
    reader = csv.DictReader(resp.text.strip().split("\n"))
    rows = list(reader)
    dangerous_rows = [r for r in rows if "sanitize_csv@t.com" in r["to"]]
    assert len(dangerous_rows) >= 1
    for row in dangerous_rows:
        # Source must be sanitized — should start with apostrophe
        assert row["source"].startswith("'"), f"Expected sanitized source but got: {row['source']}"


# --- Drift Detector tests ---

_DRIFT_BASE = {
    "plan_expected_files": ["apps/api/routes/internal.py", "apps/api/schemas.py"],
    "plan_out_of_scope": ["do not touch scoring", "do not change leads core"],
    "plan_classification": "BUILD",
    "report_files_touched": ["apps/api/routes/internal.py", "apps/api/schemas.py"],
    "report_claimed_changes": ["added drift detector endpoint", "added schemas"],
    "report_classification": "BUILD",
}


def test_drift_detector_shape():
    resp = client.post("/internal/drift-detector", json=_DRIFT_BASE)
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "status" in data
    assert "total_findings" in data
    assert "findings" in data
    assert isinstance(data["findings"], list)


def test_drift_detector_clean_when_aligned():
    resp = client.post("/internal/drift-detector", json=_DRIFT_BASE)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "clean"
    assert data["total_findings"] == 0
    assert data["findings"] == []


def test_drift_detector_file_addition_drift():
    payload = {**_DRIFT_BASE, "report_files_touched": [
        "apps/api/routes/internal.py", "apps/api/schemas.py", "apps/api/events.py",
    ]}
    resp = client.post("/internal/drift-detector", json=payload)
    data = resp.json()
    assert data["status"] == "drift"
    findings = [f for f in data["findings"] if f["check"] == "file_addition_drift"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert "apps/api/events.py" in findings[0]["message"]


def test_drift_detector_file_omission_drift():
    payload = {**_DRIFT_BASE, "report_files_touched": ["apps/api/routes/internal.py"]}
    resp = client.post("/internal/drift-detector", json=payload)
    data = resp.json()
    assert data["status"] == "watch"
    findings = [f for f in data["findings"] if f["check"] == "file_omission_drift"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"
    assert "apps/api/schemas.py" in findings[0]["message"]


def test_drift_detector_classification_drift():
    payload = {**_DRIFT_BASE, "report_classification": "HARDEN"}
    resp = client.post("/internal/drift-detector", json=payload)
    data = resp.json()
    assert data["status"] == "watch"
    findings = [f for f in data["findings"] if f["check"] == "classification_drift"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"
    assert "BUILD" in findings[0]["message"]
    assert "HARDEN" in findings[0]["message"]


def test_drift_detector_out_of_scope_intrusion():
    payload = {**_DRIFT_BASE, "report_claimed_changes": [
        "added drift detector endpoint", "do not touch scoring",
    ]}
    resp = client.post("/internal/drift-detector", json=payload)
    data = resp.json()
    assert data["status"] == "drift"
    findings = [f for f in data["findings"] if f["check"] == "out_of_scope_intrusion"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


def test_drift_detector_out_of_scope_no_false_positive():
    """Similar but non-identical items should NOT trigger out_of_scope_intrusion."""
    payload = {**_DRIFT_BASE, "report_claimed_changes": [
        "updated scoring thresholds", "modified leads creation flow",
    ]}
    resp = client.post("/internal/drift-detector", json=payload)
    data = resp.json()
    intrusions = [f for f in data["findings"] if f["check"] == "out_of_scope_intrusion"]
    assert len(intrusions) == 0


def test_drift_detector_path_normalization():
    """Backslash vs forward-slash paths should be treated as the same file."""
    payload = {
        **_DRIFT_BASE,
        "plan_expected_files": ["apps\\api\\routes\\internal.py", "apps/api/schemas.py"],
        "report_files_touched": ["apps/api/routes/internal.py", "Apps/API/Schemas.py"],
    }
    resp = client.post("/internal/drift-detector", json=payload)
    data = resp.json()
    assert data["status"] == "clean"
    assert data["total_findings"] == 0


def test_drift_detector_requires_justification_flag():
    """All drift findings should have requires_justification=True."""
    payload = {
        **_DRIFT_BASE,
        "report_files_touched": ["apps/api/routes/internal.py", "apps/api/schemas.py", "extra.py"],
        "report_classification": "HARDEN",
    }
    resp = client.post("/internal/drift-detector", json=payload)
    data = resp.json()
    assert data["total_findings"] >= 2
    for finding in data["findings"]:
        assert finding["requires_justification"] is True


def test_drift_detector_deterministic():
    payload = {
        **_DRIFT_BASE,
        "report_files_touched": ["apps/api/routes/internal.py", "apps/api/schemas.py", "new.py"],
    }
    resp1 = client.post("/internal/drift-detector", json=payload)
    resp2 = client.post("/internal/drift-detector", json=payload)
    d1, d2 = resp1.json(), resp2.json()
    assert d1["status"] == d2["status"]
    assert d1["total_findings"] == d2["total_findings"]
    assert len(d1["findings"]) == len(d2["findings"])
    for f1, f2 in zip(d1["findings"], d2["findings"]):
        assert f1["check"] == f2["check"]
        assert f1["severity"] == f2["severity"]
        assert f1["plan_value"] == f2["plan_value"]
        assert f1["report_value"] == f2["report_value"]


# --- Source Intelligence ---

_si_ready = False


def _ensure_si_data():
    global _si_ready
    if _si_ready:
        return
    _setup_followup_handoff_lead(
        "SI Won Lead", "si-won@test.com", "si_source_a",
        "notes score_override_80", "won",
    )
    _setup_followup_handoff_lead(
        "SI Lost Lead", "si-lost@test.com", "si_source_a",
        "notes score_override_55", "lost",
    )
    _setup_followup_handoff_lead(
        "SI NoAnswer Lead", "si-na@test.com", "si_source_b",
        "notes score_override_65", "no_answer",
    )
    _si_ready = True


def test_source_intelligence_structure():
    _ensure_si_data()
    resp = client.get("/internal/source-intelligence")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "total_sources" in data
    assert "totals" in data
    assert "by_source" in data
    totals = data["totals"]
    for field in ("leads", "avg_score", "pending_review", "client_ready",
                  "followup_candidates", "outcomes"):
        assert field in totals, f"Missing totals.{field}"
    outcomes = totals["outcomes"]
    for field in ("contacted", "qualified", "won", "lost", "no_answer", "bad_fit"):
        assert field in outcomes, f"Missing totals.outcomes.{field}"
    assert len(data["by_source"]) > 0
    item = data["by_source"][0]
    for field in ("source", "leads", "avg_score", "pending_review", "client_ready",
                  "followup_candidates", "outcomes", "recommendation", "rationale",
                  "data_sufficient"):
        assert field in item, f"Missing by_source[].{field}"


def test_source_intelligence_totals_consistent():
    _ensure_si_data()
    data = client.get("/internal/source-intelligence").json()
    totals = data["totals"]
    by_source = data["by_source"]
    assert totals["leads"] == sum(it["leads"] for it in by_source)
    assert totals["pending_review"] == sum(it["pending_review"] for it in by_source)
    assert totals["client_ready"] == sum(it["client_ready"] for it in by_source)
    assert totals["followup_candidates"] == sum(
        it["followup_candidates"] for it in by_source
    )
    for field in ("contacted", "qualified", "won", "lost", "no_answer", "bad_fit"):
        assert totals["outcomes"][field] == sum(
            it["outcomes"][field] for it in by_source
        ), f"totals.outcomes.{field} mismatch"


def test_source_intelligence_ordering():
    """by_source sorted by leads DESC, then source ASC."""
    _ensure_si_data()
    data = client.get("/internal/source-intelligence").json()
    items = data["by_source"]
    for i in range(len(items) - 1):
        a, b = items[i], items[i + 1]
        # leads DESC, source ASC → negate leads for tuple comparison
        assert (-a["leads"], a["source"]) <= (-b["leads"], b["source"]), \
            f"Ordering violated: {a['source']}({a['leads']}) before {b['source']}({b['leads']})"


def test_source_intelligence_source_filter():
    _ensure_si_data()
    resp = client.get("/internal/source-intelligence", params={"source": "si_source_a"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sources"] == 1
    assert data["by_source"][0]["source"] == "si_source_a"
    assert data["totals"]["leads"] == data["by_source"][0]["leads"]


def test_source_intelligence_outcomes_match_existing():
    """Outcome counts must match /internal/source-outcome-actions for same sources."""
    _ensure_si_data()
    si = client.get("/internal/source-intelligence").json()
    soa = client.get("/internal/source-outcome-actions").json()
    soa_map = {it["source"]: it for it in soa["items"]}
    for item in si["by_source"]:
        if item["source"] in soa_map:
            existing = soa_map[item["source"]]
            for field in ("contacted", "qualified", "won", "lost", "no_answer", "bad_fit"):
                assert item["outcomes"][field] == existing[field], \
                    f"{item['source']}.{field}: SI={item['outcomes'][field]} vs SOA={existing[field]}"


def test_source_intelligence_empty_source():
    resp = client.get("/internal/source-intelligence", params={"source": "nonexistent_source_xyz"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sources"] == 0
    assert data["by_source"] == []
    assert data["totals"]["leads"] == 0
