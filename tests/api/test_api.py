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
