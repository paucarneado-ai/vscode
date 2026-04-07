"""In-memory fixed-window rate limiter for public intake endpoints.

Design:
    Per-IP fixed window: max N requests per window_seconds.
    State encapsulated in RateLimiter class, instantiated once at module level.
    Stale entries cleaned on each check (no background thread).
    Applied as a FastAPI dependency on public routers.

IP extraction:
    Uses X-Forwarded-For first (set by Caddy/Traefik), falls back to client.host.
    Only the FIRST address in X-Forwarded-For is used (closest to client).
    This is acceptable because:
      - uvicorn binds to 127.0.0.1 (not reachable from outside)
      - Caddy is the only upstream and sets X-Forwarded-For correctly
      - Traefik (EasyPanel) adds its own forwarding before Caddy
    NOT safe if the app is exposed directly to the internet without a proxy.

Limitations:
    - In-memory: resets on process restart (acceptable for single-worker MVP).
    - Single process only: no cross-worker coordination (we run --workers 1).
    - No per-user or per-session tracking, only per-IP.
    - Fixed window: a client can send up to 2x limit across a window boundary.
"""

import math
import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from apps.api.config import settings


def _get_client_ip(request: Request) -> str:
    """Extract client IP from X-Forwarded-For or direct connection."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """Fixed-window per-IP rate limiter with encapsulated state."""

    def __init__(self) -> None:
        # {ip: [timestamp, timestamp, ...]}
        self._log: dict[str, list[float]] = {}

    def check(self, ip: str, max_requests: int, window: int) -> int | None:
        """Check if IP is within rate limit.

        Returns None if allowed, or seconds until retry if blocked.
        """
        now = time.monotonic()
        cutoff = now - window

        entries = self._log.get(ip, [])
        entries = [t for t in entries if t > cutoff]

        if len(entries) >= max_requests:
            # Earliest entry that will expire
            oldest_in_window = entries[0]
            retry_after = math.ceil((oldest_in_window + window) - now)
            self._log[ip] = entries
            return max(retry_after, 1)

        entries.append(now)
        self._log[ip] = entries

        # Periodic cleanup
        if len(self._log) > 200:
            stale = [k for k, v in self._log.items() if not v or v[-1] < cutoff]
            for k in stale:
                del self._log[k]

        return None

    def reset(self) -> None:
        """Clear all state. For testing only."""
        self._log.clear()


# Module-level instance — single process, single worker
_limiter = RateLimiter()


def require_rate_limit(request: Request) -> None:
    """FastAPI dependency that enforces per-IP rate limiting.

    Returns normally if allowed.
    Raises 429 with Retry-After header if limit exceeded.
    """
    max_requests = settings.rate_limit_max
    window = settings.rate_limit_window_seconds

    if max_requests <= 0:
        return  # Rate limiting disabled

    ip = _get_client_ip(request)
    retry_after = _limiter.check(ip, max_requests, window)

    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({max_requests} requests per {window}s). Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )


def reset_rate_limit_state() -> None:
    """Clear all rate limit state. For testing only."""
    _limiter.reset()


def get_limiter() -> RateLimiter:
    """Access the module limiter instance. For testing only."""
    return _limiter
