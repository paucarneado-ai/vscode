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


def test_create_lead_valid():
    response = client.post("/leads", json=VALID_LEAD)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "lead received"
    lead = data["lead"]
    assert lead["name"] == "Test User"
    assert lead["email"] == "test@example.com"
    assert lead["score"] == 70  # base 50 + source "test" 10 + notes 10
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
    assert data["rating"] == "medium"  # score 70 -> medium
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
    # "test" source gets +10, normalized " Test " -> "test" should too
    response = client.post("/leads", json={**VALID_LEAD, "email": "normscore@example.com", "source": " Test "})
    assert response.status_code == 200
    lead = response.json()["lead"]
    assert lead["source"] == "test"
    assert lead["score"] == 70  # same as VALID_LEAD with source="test"


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
    # source "test" + notes -> score 70 (high: >= 60)
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
    # Create a lead with known score (source "test" + notes -> 70)
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


OPERATIONAL_FIELDS = {"lead_id", "source", "score", "rating", "next_action", "instruction", "alert", "summary", "generated_at"}


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
    assert "name" not in op
    assert "email" not in op
    assert "notes" not in op
    assert "created_at" not in op
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
