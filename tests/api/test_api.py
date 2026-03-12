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
    assert isinstance(data["message"], str)
    assert isinstance(data["pack"], dict)

    # Pack has all expected fields
    pack = data["pack"]
    for field in ["lead_id", "created_at", "name", "email", "source", "notes", "score", "rating", "summary"]:
        assert field in pack, f"missing field '{field}' in pack"


def test_get_lead_delivery_pack_consistent_with_standalone():
    r = client.post("/leads", json={**VALID_LEAD, "email": "delcon@delivery.com", "source": "del_consist"})
    lead_id = r.json()["lead"]["id"]

    pack_resp = client.get(f"/leads/{lead_id}/pack").json()
    delivery_resp = client.get(f"/leads/{lead_id}/delivery").json()

    # Embedded pack should match standalone pack
    assert delivery_resp["pack"] == pack_resp


def test_get_lead_delivery_generated_at_matches_created():
    r = client.post("/leads", json={**VALID_LEAD, "email": "deltime@delivery.com", "source": "del_time"})
    lead_id = r.json()["lead"]["id"]

    data = client.get(f"/leads/{lead_id}/delivery").json()
    assert data["generated_at"] == data["pack"]["created_at"]


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
    # Edge: " " passes min_length=1 but strip() gives "".
    # Documenting current behavior — source is stored as empty string.
    r = client.post("/leads", json={**VALID_LEAD, "email": "ws@contract.com", "source": " "})
    assert r.status_code == 200
    assert r.json()["lead"]["source"] == ""


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
