"""Tests for API key authentication."""

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
from apps.api.ratelimit import reset_rate_limit_state

import apps.api.auth as auth_module
import apps.api.config as config_module

TEST_API_KEY = "test-secret-key-12345"

client = TestClient(app)


def _set_auth(api_key: str, app_env: str = "development"):
    """Temporarily configure auth state for testing."""
    orig_key = config_module.settings.api_key
    orig_env = config_module.settings.app_env
    # Frozen dataclass — use object.__setattr__
    object.__setattr__(config_module.settings, "api_key", api_key)
    object.__setattr__(config_module.settings, "app_env", app_env)
    auth_module._auth_bypassed = not api_key and app_env in auth_module._AUTH_BYPASS_ENVS
    return orig_key, orig_env


def _restore_auth(orig_key: str, orig_env: str):
    object.__setattr__(config_module.settings, "api_key", orig_key)
    object.__setattr__(config_module.settings, "app_env", orig_env)
    auth_module._auth_bypassed = not orig_key and orig_env in auth_module._AUTH_BYPASS_ENVS


# ============================================================
# Auth ENABLED (key configured)
# ============================================================

class TestAuthEnabled:

    def setup_method(self):
        reset_rate_limit_state()
        self.orig = _set_auth(TEST_API_KEY, "production")

    def teardown_method(self):
        _restore_auth(*self.orig)

    # --- Authorized ---
    def test_queue_with_key(self):
        assert client.get("/internal/queue", headers={"X-API-Key": TEST_API_KEY}).status_code == 200

    def test_leads_with_key(self):
        assert client.get("/leads", headers={"X-API-Key": TEST_API_KEY}).status_code == 200

    def test_summary_with_key(self):
        assert client.get("/leads/summary", headers={"X-API-Key": TEST_API_KEY}).status_code == 200

    def test_create_with_key(self):
        r = client.post("/leads", json={"name": "A", "email": "a@a.com", "source": "test"},
                        headers={"X-API-Key": TEST_API_KEY})
        assert r.status_code in (200, 409)

    # --- Missing key ---
    def test_queue_no_key(self):
        assert client.get("/internal/queue").status_code == 401

    def test_leads_no_key(self):
        assert client.get("/leads").status_code == 401

    def test_create_no_key(self):
        assert client.post("/leads", json={"name": "B", "email": "b@b.com", "source": "test"}).status_code == 401

    # --- Wrong key ---
    def test_queue_bad_key(self):
        assert client.get("/internal/queue", headers={"X-API-Key": "wrong"}).status_code == 403

    def test_leads_bad_key(self):
        assert client.get("/leads", headers={"X-API-Key": "wrong"}).status_code == 403

    # --- Public endpoints always accessible ---
    def test_health_no_key(self):
        assert client.get("/health").status_code == 200

    def test_intake_no_key(self):
        r = client.post("/leads/intake/web", json={
            "nombre": "Pub", "email": "pub@t.com", "telefono": "", "interes": "",
        })
        assert r.status_code in (200, 409)

    def test_health_with_key(self):
        assert client.get("/health", headers={"X-API-Key": TEST_API_KEY}).status_code == 200

    def test_intake_with_key(self):
        r = client.post("/leads/intake/web", json={
            "nombre": "PubK", "email": "pubk@t.com", "telefono": "", "interes": "",
        }, headers={"X-API-Key": TEST_API_KEY})
        assert r.status_code in (200, 409)

    # --- Timing-safe comparison (functional, not a timing test) ---
    def test_near_miss_key_rejected(self):
        """A key that differs by one char must be rejected."""
        bad = TEST_API_KEY[:-1] + ("x" if TEST_API_KEY[-1] != "x" else "y")
        assert client.get("/leads", headers={"X-API-Key": bad}).status_code == 403


# ============================================================
# Auth DISABLED (dev mode — no key, APP_ENV=development)
# ============================================================

class TestAuthDisabledDev:

    def setup_method(self):
        self.orig = _set_auth("", "development")

    def teardown_method(self):
        _restore_auth(*self.orig)

    def test_queue_accessible(self):
        assert client.get("/internal/queue").status_code == 200

    def test_leads_accessible(self):
        assert client.get("/leads").status_code == 200

    def test_health_accessible(self):
        assert client.get("/health").status_code == 200


# ============================================================
# Auth DISABLED (test mode — no key, APP_ENV=test)
# ============================================================

class TestAuthDisabledTest:

    def setup_method(self):
        self.orig = _set_auth("", "test")

    def teardown_method(self):
        _restore_auth(*self.orig)

    def test_queue_accessible(self):
        assert client.get("/internal/queue").status_code == 200


# ============================================================
# FAIL-CLOSED (production, no key configured)
# ============================================================

class TestFailClosed:

    def setup_method(self):
        reset_rate_limit_state()
        self.orig = _set_auth("", "production")

    def teardown_method(self):
        _restore_auth(*self.orig)

    def test_queue_rejects_503(self):
        assert client.get("/internal/queue").status_code == 503

    def test_leads_rejects_503(self):
        assert client.get("/leads").status_code == 503

    def test_health_still_works(self):
        assert client.get("/health").status_code == 200

    def test_intake_still_works(self):
        r = client.post("/leads/intake/web", json={
            "nombre": "Fail", "email": "fail@t.com", "telefono": "", "interes": "",
        })
        assert r.status_code in (200, 409)
