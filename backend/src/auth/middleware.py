"""
src/auth/middleware.py
──────────────────────
Transparent token rotation middleware.

On every secured request:
  1. If the access token is valid and not near expiry → pass through untouched.
  2. If the access token is expired/missing BUT a valid refresh token exists
     with sufficient remaining lifetime → rotate silently:
       - Issue new access + refresh token pair
       - Set new cookies on the response
       - Inject the new access token data into request.state so downstream
         dependencies (CookieTokenBearer) read the fresh token, not the stale one
  3. If rotation is not possible (refresh expired, blocklisted, not in store,
     or on an auth management route) → pass through and let the normal
     dependency handle the 401/403.

Rotation threshold:
  REFRESH_MIN_TTL_SECONDS — minimum remaining lifetime the refresh token must
  have before we consider rotating. Below this the refresh is nearly expired
  and rotation would produce a very short-lived pair; better to let the user
  re-authenticate.

Routes excluded from rotation:
  AUTH_BYPASS_PATHS — the auth management endpoints handle their own token
  logic and must not be intercepted.
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from src.config import Config
from src.auth.utils import decode_token, seconds_until_expiry
from src.auth.service import auth_service as _auth_service
from src.db.redis_client import (
    token_in_blocklist,
    get_refresh_token_owner,
    delete_refresh_token,
    add_jti_to_blocklist,
)
from src.db.main import get_session_context

logger = logging.getLogger(__name__)

# Only attempt rotation when the refresh token has at least this much life left.
# Below this threshold the session is nearly over — let the user re-authenticate.
REFRESH_MIN_TTL_SECONDS = 60 * 60 * 24 * 2  # 2 days

# These endpoints manage their own token logic — never intercept them.
AUTH_BYPASS_PATHS = {
    "/auth/login",
    "/auth/logout",
    "/auth/signup",
    "/auth/refresh_token",
}



class TokenRefreshMiddleware(BaseHTTPMiddleware):
    """
    Silently rotates the token pair when the access token is expired but the
    refresh token is still valid with sufficient remaining lifetime.

    Injects the new access token data into request.state.token_data so that
    CookieTokenBearer can read it without re-decoding the (now stale) cookie.
    The new cookies are written onto the response.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip auth management routes
        if request.url.path in AUTH_BYPASS_PATHS:
            return await call_next(request)

        access_token = request.cookies.get("access_token")
        refresh_token = request.cookies.get("refresh_token")

        # If access token is present and valid, nothing to do
        if access_token:
            token_data = decode_token(access_token)
            if token_data:
                try:
                    if not await token_in_blocklist(token_data["jti"]):
                        return await call_next(request)
                except Exception:
                    logger.warning("Redis check failed during token validation", exc_info=True)

        # Access token is absent, expired, or invalid.
        # Attempt silent rotation using the refresh token.
        if not refresh_token:
            return await call_next(request)

        refresh_data = decode_token(refresh_token)
        if not refresh_data:
            return await call_next(request)

        # Verify it's actually a refresh token
        if not refresh_data.get("refresh"):
            return await call_next(request)

        # Check refresh token has enough life left
        refresh_ttl = seconds_until_expiry(refresh_data)
        if refresh_ttl < REFRESH_MIN_TTL_SECONDS:
            return await call_next(request)

        # Verify the refresh JTI is in our store (wasn't already rotated)
        jti = refresh_data["jti"]
        if await token_in_blocklist(jti):
            return await call_next(request)

        owner = await get_refresh_token_owner(jti)
        if not owner or owner != refresh_data["user"]["username"]:
            return await call_next(request)

        # All checks passed — rotate
        try:
            async with get_session_context() as session:
                user = await _auth_service.get_user_with_username(
                    refresh_data["user"]["username"], session
                )

            if not user:
                return await call_next(request)

            # Invalidate the old refresh token
            await delete_refresh_token(jti)
            await add_jti_to_blocklist(jti, max(refresh_ttl, 1))

            # Issue a new pair
            new_access_token, new_refresh_token = await _auth_service.generate_tokens(
                user
            )

            # Inject the new token data into request state so CookieTokenBearer
            # reads the fresh token rather than the expired cookie
            new_token_data = decode_token(new_access_token)
            request.state.rotated_token_data = new_token_data

            # Process the request with the new token in state
            response = await call_next(request)

            # Write the new cookies onto the response
            response.set_cookie(
                key="access_token",
                value=new_access_token,
                httponly=True,
                secure=Config.cookie_secure,
                samesite="lax",
            )
            response.set_cookie(
                key="refresh_token",
                value=new_refresh_token,
                httponly=True,
                secure=Config.cookie_secure,
                samesite="lax",
            )
            return response

        except Exception:
            # Rotation failed for any reason — log it loudly so silent bugs
            # like the previous Config NameError can't hide. Then pass through
            # and let the normal dependency chain handle the auth failure.
            logger.exception("token rotation failed")
            return await call_next(request)
