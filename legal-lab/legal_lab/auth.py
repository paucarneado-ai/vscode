"""API key authentication for protected endpoints.

Set LEGAL_LAB_API_KEY environment variable.
Behavior depends on APP_ENV:
  - development/test: auth disabled if no key set
  - any other value: auth REQUIRED, missing key = all protected requests rejected

Bypass eligibility is computed at request time (not import time) so that
settings changes in tests take effect without mutating module-level state.
"""

import logging
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from legal_lab.config import settings

logger = logging.getLogger(__name__)

_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

_AUTH_BYPASS_ENVS = {"development", "test"}


def require_api_key(api_key: str | None = Security(_header_scheme)) -> str:
    """Validate X-API-Key header. Returns the key on success.

    401 if missing, 403 if invalid, 503 if production key not configured.
    In dev/test with no key configured, allows all requests.
    """
    if not settings.api_key and settings.app_env in _AUTH_BYPASS_ENVS:
        return ""

    if not settings.api_key:
        raise HTTPException(status_code=503, detail="Server auth not configured")

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    if not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key
