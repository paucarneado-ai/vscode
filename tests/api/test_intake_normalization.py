"""Tests for intake normalization helpers and Meta/n8n ingestion path."""

import tempfile

import apps.api.db as db_module

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
db_module.DATABASE_PATH = _tmp.name
db_module.reset_db()
db_module.init_db()

import pytest
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.schemas import WebIntakePayload, WebhookLeadPayload
from apps.api.services.intake import (
    normalize_web_intake,
    normalize_webhook_payload,
    ProviderValidationError,
)

client = TestClient(app)


# --- normalize_web_intake ---

class TestNormalizeWebIntake:

    def test_assembles_notes_from_fields(self):
        payload = WebIntakePayload(
            nombre="Test", email="t@t.com",
            telefono="+34600000000", interes="velero", mensaje="12m Bavaria",
        )
        result = normalize_web_intake(payload)
        assert result.name == "Test"
        assert result.email == "t@t.com"
        assert "Teléfono: +34600000000" in result.notes
        assert "Interés: velero" in result.notes
        assert "Mensaje: 12m Bavaria" in result.notes

    def test_default_source(self):
        payload = WebIntakePayload(nombre="Test", email="t@t.com")
        result = normalize_web_intake(payload)
        assert result.source == "web:sentyacht"

    def test_custom_origen(self):
        payload = WebIntakePayload(nombre="Test", email="t@t.com", origen="web:sentyacht-vender:A")
        result = normalize_web_intake(payload)
        assert result.source == "web:sentyacht-vender:a"

    def test_empty_origen_falls_back(self):
        payload = WebIntakePayload(nombre="Test", email="t@t.com", origen="  ")
        result = normalize_web_intake(payload)
        assert result.source == "web:sentyacht"

    def test_no_optional_fields_gives_no_notes(self):
        payload = WebIntakePayload(nombre="Test", email="t@t.com")
        result = normalize_web_intake(payload)
        assert result.notes is None


# --- normalize_webhook_payload ---

class TestNormalizeWebhookPayload:

    def test_basic_normalization(self):
        payload = WebhookLeadPayload(name="Test", email="t@t.com", notes="some notes")
        result = normalize_webhook_payload("my-provider", payload)
        assert result.source == "webhook:my-provider"
        assert result.name == "Test"
        assert result.notes == "some notes"

    def test_provider_normalized(self):
        payload = WebhookLeadPayload(name="T", email="t@t.com")
        result = normalize_webhook_payload("  Meta-Instant  ", payload)
        assert result.source == "webhook:meta-instant"

    def test_empty_provider_raises(self):
        payload = WebhookLeadPayload(name="T", email="t@t.com")
        with pytest.raises(ProviderValidationError):
            normalize_webhook_payload("  ", payload)

    def test_notes_passthrough(self):
        payload = WebhookLeadPayload(name="T", email="t@t.com", notes=None)
        result = normalize_webhook_payload("test", payload)
        assert result.notes is None


# --- Meta/n8n ingestion via webhook endpoint ---

class TestMetaN8nIngestion:
    """Tests simulating n8n posting Meta Lead Ads data to the webhook endpoint."""

    META_PROVIDER = "meta-instant"

    def test_meta_lead_accepted(self):
        """n8n sends a transformed Meta lead via webhook."""
        resp = client.post(
            f"/leads/webhook/{self.META_PROVIDER}",
            json={
                "name": "Carlos Garcia",
                "email": "carlos.garcia@example.com",
                "notes": "Tipo: Yate a motor\nEslora: 15m\nPuerto: Barcelona\nDetalles: Azimut 50, 2018",
            },
            headers={"X-API-Key": ""},  # Dev mode
        )
        assert resp.status_code in (200, 409)
        data = resp.json()
        assert data.get("status") in ("accepted", "duplicate")
        assert "lead_id" in data

    def test_meta_lead_source_correct(self):
        """Lead created from Meta webhook should have source=webhook:meta-instant."""
        resp = client.post(
            f"/leads/webhook/{self.META_PROVIDER}",
            json={
                "name": "Meta Source Test",
                "email": "meta-source@test.com",
                "notes": "Tipo: Velero",
            },
            headers={"X-API-Key": ""},
        )
        lead_id = resp.json()["lead_id"]
        lead = client.get(f"/leads/{lead_id}", headers={"X-API-Key": ""}).json()
        assert lead["source"] == "webhook:meta-instant"

    def test_meta_lead_duplicate_handling(self):
        """Same email+source from Meta should return 409."""
        payload = {
            "name": "Dup Meta",
            "email": "dup-meta@test.com",
            "notes": "test",
        }
        r1 = client.post(f"/leads/webhook/{self.META_PROVIDER}", json=payload, headers={"X-API-Key": ""})
        assert r1.status_code in (200, 409)
        r2 = client.post(f"/leads/webhook/{self.META_PROVIDER}", json=payload, headers={"X-API-Key": ""})
        assert r2.status_code == 409
        assert r2.json()["status"] == "duplicate"

    def test_meta_lead_with_structured_notes_scores_well(self):
        """A Meta lead with structured notes should score higher than minimal."""
        resp = client.post(
            f"/leads/webhook/{self.META_PROVIDER}",
            json={
                "name": "Scored Meta Lead",
                "email": "scored-meta@test.com",
                "notes": "Teléfono: +34600111222\nTipo: Yate a motor\nEslora: 18m\nPrecio orientativo: 500000",
            },
            headers={"X-API-Key": ""},
        )
        lead_id = resp.json()["lead_id"]
        lead = client.get(f"/leads/{lead_id}", headers={"X-API-Key": ""}).json()
        assert lead["score"] >= 50  # Should benefit from phone + type + eslora + price

    def test_meta_batch_ingestion(self):
        """n8n batch webhook for multiple Meta leads."""
        resp = client.post(
            f"/leads/webhook/{self.META_PROVIDER}/batch",
            json=[
                {"name": "Batch Meta 1", "email": "batch-meta-1@test.com", "notes": "Tipo: Velero"},
                {"name": "Batch Meta 2", "email": "batch-meta-2@test.com", "notes": "Tipo: Lancha"},
            ],
            headers={"X-API-Key": ""},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["created"] >= 1

    def test_meta_minimal_payload(self):
        """Meta lead with only name+email (no notes) should still be accepted."""
        resp = client.post(
            f"/leads/webhook/{self.META_PROVIDER}",
            json={"name": "Minimal Meta", "email": "minimal-meta@test.com"},
            headers={"X-API-Key": ""},
        )
        assert resp.status_code in (200, 409)
