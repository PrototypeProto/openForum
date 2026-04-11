"""
src/rate_limit.py
─────────────────
Rate limiting via Redis INCR + EXPIRE.

Usage — add as a FastAPI dependency on any route:

    from src.rate_limit import rate_limit

    @router.post("/login")
    async def login(
        request: Request,
        _: None = Depends(rate_limit("auth:login", limit=10, window=60)),
    ):
        ...

How it works:
  1. Identify the caller — by username for authenticated requests (more
     accurate), by IP for unauthenticated ones (login, signup).
  2. INCR a namespaced Redis key. On the first hit, set EXPIRE = window.
  3. If count > limit, raise RateLimitError with a Retry-After header.

The identifier is sourced from:
  - request.state.rotated_token_data  (middleware already rotated the token)
  - the access_token cookie           (still valid, not yet rotated)
  - the client IP                     (fallback for unauthenticated routes)

Key format:  rate:<identifier>:<route_key>
TTL:         window_seconds (auto-cleaned by Redis)
"""

import logging

from fastapi import Depends, Request, Response

from src.auth.utils import decode_token
from src.config import Config
from src.db.redis_client import check_rate_limit, get_rate_limit_ttl
from src.exceptions import RateLimitError

logger = logging.getLogger(__name__)


def _get_identifier(request: Request) -> str:
    """
    Return a string that identifies the caller for rate limiting.

    Prefer username (more stable than IP, correctly handles proxies),
    fall back to IP for unauthenticated requests.
    """
    # Check if middleware already decoded a rotated token
    rotated = getattr(request.state, "rotated_token_data", None)
    if rotated:
        return f"user:{rotated['user']['username']}"

    # Try the access token cookie
    token = request.cookies.get("access_token")
    if token:
        data = decode_token(token)
        if data:
            return f"user:{data['user']['username']}"

    # Fall back to IP — handles login, signup, public endpoints
    # X-Forwarded-For is set by reverse proxies (nginx, Caddy, etc.)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first (original client) IP from the chain
        ip = forwarded_for.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    return f"ip:{ip}"


def rate_limit(route_key: str, limit: int, window: int):
    """
    FastAPI dependency factory for rate limiting.

    Args:
        route_key:  Short stable identifier for the endpoint, e.g. "auth:login".
                    Used as part of the Redis key — keep it lowercase with colons.
        limit:      Maximum number of requests allowed in the window.
        window:     Window duration in seconds.

    Returns a dependency that raises RateLimitError (429) when the limit
    is exceeded. On success it adds rate limit headers to the response.

    Example:
        Depends(rate_limit("auth:login", limit=10, window=60))
        → 10 requests per 60 seconds per identifier
    """

    async def _check(request: Request, response: Response) -> None:
        # Bypass entirely in testing (or when explicitly disabled via env var).
        # This prevents flaky 429s when a test makes multiple calls to the
        # same endpoint inside a single test function.
        if Config.DISABLE_RATE_LIMIT:
            return

        try:
            identifier = _get_identifier(request)
            count, remaining = await check_rate_limit(
                identifier=identifier,
                route_key=route_key,
                limit=limit,
                window_seconds=window,
            )
        except Exception:
            # Redis is down — fail open. Rate limiting is a defence layer,
            # not core functionality. Log so we notice, but don't block
            # every request because the cache is unreachable.
            logger.warning("rate limit check failed (Redis unavailable?)", exc_info=True)
            return

        # Always add informational headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = str(window)

        if count > limit:
            try:
                retry_after = await get_rate_limit_ttl(identifier, route_key)
            except Exception:
                retry_after = window
            response.headers["Retry-After"] = str(retry_after)
            raise RateLimitError(f"Rate limit exceeded. Try again in {retry_after} seconds.")

    return Depends(_check)
