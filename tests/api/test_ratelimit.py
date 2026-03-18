"""Tests for rate limiting on public intake endpoints."""

import tempfile

import apps.api.db as db_module

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
db_module.DATABASE_PATH = _tmp.name
db_module.reset_db()
db_module.init_db()

import apps.api.config as config_module
from apps.api.ratelimit import reset_rate_limit_state, get_limiter, RateLimiter

from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

INTAKE_PAYLOAD = {
    "nombre": "Rate Test",
    "email": "rate@test.com",
    "telefono": "",
    "interes": "",
}


def _set_limits(max_req: int, window: int):
    orig_max = config_module.settings.rate_limit_max
    orig_window = config_module.settings.rate_limit_window_seconds
    object.__setattr__(config_module.settings, "rate_limit_max", max_req)
    object.__setattr__(config_module.settings, "rate_limit_window_seconds", window)
    return orig_max, orig_window


def _restore_limits(orig_max: int, orig_window: int):
    object.__setattr__(config_module.settings, "rate_limit_max", orig_max)
    object.__setattr__(config_module.settings, "rate_limit_window_seconds", orig_window)


# --- RateLimiter unit tests ---

class TestRateLimiterUnit:

    def test_allows_within_limit(self):
        rl = RateLimiter()
        assert rl.check("1.1.1.1", 3, 60) is None
        assert rl.check("1.1.1.1", 3, 60) is None
        assert rl.check("1.1.1.1", 3, 60) is None

    def test_blocks_over_limit(self):
        rl = RateLimiter()
        for _ in range(5):
            rl.check("1.1.1.1", 5, 60)
        retry = rl.check("1.1.1.1", 5, 60)
        assert retry is not None
        assert retry >= 1

    def test_separate_ips(self):
        rl = RateLimiter()
        for _ in range(3):
            rl.check("a", 3, 60)
        assert rl.check("a", 3, 60) is not None  # blocked
        assert rl.check("b", 3, 60) is None  # different IP, allowed

    def test_reset_clears_state(self):
        rl = RateLimiter()
        for _ in range(5):
            rl.check("x", 5, 60)
        assert rl.check("x", 5, 60) is not None
        rl.reset()
        assert rl.check("x", 5, 60) is None  # cleared


# --- Integration tests ---

class TestRateLimit:

    def setup_method(self):
        reset_rate_limit_state()
        self.orig = _set_limits(3, 60)

    def teardown_method(self):
        _restore_limits(*self.orig)
        reset_rate_limit_state()

    def test_normal_submission_succeeds(self):
        r = client.post("/leads/intake/web", json=INTAKE_PAYLOAD)
        assert r.status_code in (200, 409)

    def test_burst_hits_limit(self):
        statuses = []
        for i in range(5):
            p = {**INTAKE_PAYLOAD, "email": f"burst{i}@test.com"}
            r = client.post("/leads/intake/web", json=p)
            statuses.append(r.status_code)
        assert all(s in (200, 409) for s in statuses[:3])
        assert 429 in statuses[3:]

    def test_429_has_retry_after_header(self):
        for i in range(3):
            client.post("/leads/intake/web", json={**INTAKE_PAYLOAD, "email": f"hdr{i}@test.com"})
        r = client.post("/leads/intake/web", json={**INTAKE_PAYLOAD, "email": "hdr3@test.com"})
        assert r.status_code == 429
        assert "Retry-After" in r.headers
        retry = int(r.headers["Retry-After"])
        assert 1 <= retry <= 60

    def test_429_response_body(self):
        for i in range(3):
            client.post("/leads/intake/web", json={**INTAKE_PAYLOAD, "email": f"body{i}@test.com"})
        r = client.post("/leads/intake/web", json={**INTAKE_PAYLOAD, "email": "body3@test.com"})
        assert r.status_code == 429
        assert "Rate limit exceeded" in r.json()["detail"]
        assert "Try again in" in r.json()["detail"]

    def test_auth_endpoints_not_rate_limited(self):
        """Rate limit only applies to public router."""
        import apps.api.auth as auth_module
        orig_key = config_module.settings.api_key
        object.__setattr__(config_module.settings, "api_key", "")
        object.__setattr__(config_module.settings, "app_env", "development")
        auth_module._auth_bypassed = True
        try:
            for i in range(5):
                client.post("/leads/intake/web", json={**INTAKE_PAYLOAD, "email": f"auth{i}@test.com"})
            assert client.get("/leads").status_code == 200
            assert client.get("/health").status_code == 200
        finally:
            object.__setattr__(config_module.settings, "api_key", orig_key)
            object.__setattr__(config_module.settings, "app_env", "development")
            auth_module._auth_bypassed = not orig_key

    def test_disabled_when_zero(self):
        _set_limits(0, 60)
        for i in range(10):
            r = client.post("/leads/intake/web", json={**INTAKE_PAYLOAD, "email": f"nolim{i}@test.com"})
            assert r.status_code in (200, 409)


class TestRateLimitIPExtraction:

    def setup_method(self):
        reset_rate_limit_state()
        self.orig = _set_limits(2, 60)

    def teardown_method(self):
        _restore_limits(*self.orig)
        reset_rate_limit_state()

    def test_different_ips_separate_limits(self):
        for i in range(2):
            r = client.post("/leads/intake/web", json={**INTAKE_PAYLOAD, "email": f"ipa{i}@test.com"},
                            headers={"X-Forwarded-For": "1.1.1.1"})
            assert r.status_code in (200, 409)
        r = client.post("/leads/intake/web", json={**INTAKE_PAYLOAD, "email": "ipa2@test.com"},
                        headers={"X-Forwarded-For": "1.1.1.1"})
        assert r.status_code == 429
        r = client.post("/leads/intake/web", json={**INTAKE_PAYLOAD, "email": "ipb0@test.com"},
                        headers={"X-Forwarded-For": "2.2.2.2"})
        assert r.status_code in (200, 409)
