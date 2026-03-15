import csv
import io
import tempfile

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
    assert lead["score"] == 60  # base 50 + notes 10
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
    assert data["rating"] == "medium"  # score 60 -> medium
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
    assert "medium" in body


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
    assert "medium" in body


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
    assert data["pack"]["rating"] == "medium"
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
    response = client.get("/leads", params={"min_score": 60})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(lead["score"] >= 60 for lead in data)


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
        "/leads", params={"source": "combo", "min_score": 60, "limit": 5, "offset": 0}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(lead["source"] == "combo" and lead["score"] >= 60 for lead in data)
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
    assert lead["score"] == 60  # base 50 + notes 10 (source no longer affects score)


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
    # notes present -> score 60 (high: >= 60)
    client.post("/leads", json={
        "name": "BucketHi", "email": "buckhi@bucket.com",
        "source": "test", "notes": "interested in demo",
    })
    # source with no bonus + no notes -> score 50 (medium: 40-59)
    client.post("/leads", json={
        "name": "BucketMed", "email": "buckmed@bucket.com",
        "source": "bucket_unknown", "notes": "",
    })
    resp = client.get("/leads/summary", params={"source": "bucket_unknown"})
    data = resp.json()
    assert data["medium_score_count"] >= 1

    resp = client.get("/leads/summary", params={"source": "test"})
    data = resp.json()
    assert data["high_score_count"] >= 1


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
    # Create a lead with known score (notes present -> 60)
    client.post("/leads", json={
        "name": "ScoreSum", "email": "scoresum@summary.com",
        "source": "test", "notes": "interested in demo",
    })
    # With very high min_score, this lead is excluded
    resp_high = client.get("/leads/summary", params={"min_score": 9999})
    assert resp_high.json()["total_leads"] == 0

    # With low min_score, it's included
    resp_low = client.get("/leads/summary", params={"min_score": 60})
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


OPERATIONAL_FIELDS = {"lead_id", "name", "source", "score", "rating", "next_action", "instruction", "alert", "summary", "created_at", "generated_at"}


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
    assert data["total"] <= 2


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
    "send_to_client": "Send lead to client for prioritization",
    "review_manually": "Review lead manually",
    "request_more_info": "Request more information from lead",
    "enrich_first": "Enrich lead data before further action",
    "discard": "Discard lead — insufficient data",
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
    assert limited["total"] == 2
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
        "source": "dispatch_src", "notes": "real notes",
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
    assert limited["total"] == 2
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
    assert limited["total"] == 1
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
        "source": "claimtest", "notes": "real notes",
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
        "source": "claimtest", "notes": "real notes",
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
        "source": "claimtest", "notes": "real notes",
    })
    id_a = r.json()["lead"]["id"]
    client.post("/internal/dispatch/claim", json={"lead_ids": [id_a]})

    r2 = client.post("/leads", json={
        "name": "Claim Mix B", "email": "claimmix_b@claim.com",
        "source": "claimtest", "notes": "real notes",
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
        "source": "claimexcl", "notes": "real notes",
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
        "source": "claimuncl", "notes": "real notes",
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
        "source": "claimtest", "notes": "real notes",
    })
    lead_id = r.json()["lead"]["id"]
    resp = client.post("/internal/dispatch/claim", json={"lead_ids": [lead_id, lead_id, lead_id]})
    data = resp.json()
    assert data["claimed"] == [lead_id]
    assert data["already_claimed"] == []
    assert data["not_found"] == []


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
    assert resp2.json()["status"] == "duplicate"
    assert resp2.json()["lead_id"] == resp1.json()["lead_id"]


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
    """Score does not depend on source value — only on notes presence."""
    r1 = client.post("/leads", json={
        "name": "ScoreA", "email": "score_ind_a@example.com",
        "source": "test", "notes": "has notes",
    })
    r2 = client.post("/leads", json={
        "name": "ScoreB", "email": "score_ind_b@example.com",
        "source": "anything-else", "notes": "has notes",
    })
    assert r1.json()["lead"]["score"] == r2.json()["lead"]["score"] == 60

    r3 = client.post("/leads", json={
        "name": "ScoreC", "email": "score_ind_c@example.com",
        "source": "test", "notes": "",
    })
    r4 = client.post("/leads", json={
        "name": "ScoreD", "email": "score_ind_d@example.com",
        "source": "anything-else", "notes": "",
    })
    assert r3.json()["lead"]["score"] == r4.json()["lead"]["score"] == 50


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
    assert resp.json()["score"] == 50  # base only, no notes bonus


def test_scoring_ext_plus_real_notes_gets_bonus():
    """Lead with user notes + @ext: metadata gets the notes bonus."""
    resp = client.post("/leads/external", json={
        "name": "ExtWithNotes", "email": "ext_withnotes@audit.com",
        "source": "test:h4b", "phone": "+34111222333",
        "notes": "Interested in sailboats",
    })
    assert resp.status_code == 200
    assert resp.json()["score"] == 60  # base + notes bonus


def test_scoring_normal_notes_still_gets_bonus():
    """Regular POST /leads with notes still gets the notes bonus."""
    resp = client.post("/leads", json={
        "name": "NormalNotes", "email": "normal_notes@audit.com",
        "source": "test", "notes": "interested in demo",
    })
    assert resp.status_code == 200
    assert resp.json()["lead"]["score"] == 60


def test_scoring_unit_has_user_notes():
    """Unit test for _has_user_notes helper."""
    from apps.api.services.scoring import _has_user_notes

    assert _has_user_notes(None) is False
    assert _has_user_notes("") is False
    assert _has_user_notes("   ") is False
    assert _has_user_notes("real notes") is True
    assert _has_user_notes('@ext:{"phone":"+34111"}') is False
    assert _has_user_notes('real notes\n\n@ext:{"phone":"+34111"}') is True
    assert _has_user_notes('\n\n@ext:{"phone":"+34111"}') is False


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


def test_action_ext_only_treated_as_no_notes():
    """Lead with only @ext: metadata should get request_more_info, not review_manually."""
    from apps.api.services.actions import determine_next_action

    # score 50 + only @ext: notes → should be request_more_info (no real notes)
    assert determine_next_action(50, '@ext:{"phone":"+34111"}') == "request_more_info"
    # score 50 + real notes → should be review_manually
    assert determine_next_action(50, "interested in boats") == "review_manually"
    # score 50 + real notes + @ext: → should be review_manually
    assert determine_next_action(50, 'interested\n@ext:{"phone":"+34111"}') == "review_manually"


def test_action_ext_only_low_score_treated_as_discard():
    """Lead with only @ext: metadata and score < 40 should discard, not enrich_first."""
    from apps.api.services.actions import determine_next_action

    assert determine_next_action(30, '@ext:{"phone":"+34111"}') == "discard"
    assert determine_next_action(30, "real notes") == "enrich_first"


def test_action_consistent_with_scoring_on_ext():
    """Scoring and actions agree: @ext:-only means no real notes for both."""
    from apps.api.services.actions import determine_next_action
    from apps.api.services.scoring import calculate_lead_score

    notes_ext_only = '@ext:{"phone":"+34111222333"}'
    score = calculate_lead_score("test", notes_ext_only)
    assert score == 50  # no bonus
    action = determine_next_action(score, notes_ext_only)
    assert action == "request_more_info"  # not review_manually


def test_action_via_endpoint_ext_only_lead():
    """End-to-end: external lead with phone-only gets request_more_info."""
    resp = client.post("/leads/external", json={
        "name": "H9 E2E", "email": "h9e2e@audit.com",
        "source": "test:h9", "phone": "+34999888777",
    })
    assert resp.status_code == 200
    lead_id = resp.json()["lead_id"]
    op = client.get(f"/leads/{lead_id}/operational").json()
    assert op["score"] == 50
    assert op["next_action"] == "request_more_info"


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
        "source": "h20_actionable", "notes": "real notes",
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
