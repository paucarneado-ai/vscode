"""API key authentication for internal/sensitive endpoints.

Usage:
    from apps.api.auth import require_api_key

    router = APIRouter(dependencies=[Depends(require_api_key)])

Configuration:
    Set OPENCLAW_API_KEY environment variable.
    Behavior depends on APP_ENV:
      - development/test: auth disabled if no key set (with warning)
      - any other value: auth REQUIRED, missing key = startup warning + all protected requests rejected
"""

import logging
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from apps.api.config import settings

logger = logging.getLogger(__name__)

_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

# Fail-closed outside dev/test
_AUTH_BYPASS_ENVS = {"development", "test"}
_auth_bypassed = not settings.api_key and settings.app_env in _AUTH_BYPASS_ENVS

if not settings.api_key:
    if settings.app_env in _AUTH_BYPASS_ENVS:
        logger.warning("OPENCLAW_API_KEY not set — auth disabled (APP_ENV=%s)", settings.app_env)
    else:
        logger.error(
            "OPENCLAW_API_KEY not set in APP_ENV=%s — all protected endpoints will reject requests. "
            "Set OPENCLAW_API_KEY in .env.",
            settings.app_env,
        )


def require_api_key(api_key: str | None = Security(_header_scheme)) -> str:
    """FastAPI dependency that validates the X-API-Key header.

    Returns the validated key on success.
    Raises 401 if missing, 403 if invalid.
    In dev/test with no key configured, allows all requests.
    In production with no key configured, rejects all requests (fail-closed).
    """
    if _auth_bypassed:
        return ""

    if not settings.api_key:
        # Production with no key = fail-closed
        raise HTTPException(status_code=503, detail="Server auth not configured")

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    if not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key
