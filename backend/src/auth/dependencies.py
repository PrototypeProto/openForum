import logging

from fastapi import Depends, Request
from fastapi.openapi.models import APIKey, APIKeyIn
from fastapi.security.base import SecurityBase
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.enums import MemberRoleEnum
from src.db.main import get_session
from src.db.models import User
from src.db.redis_client import (
    add_jti_to_blocklist,
    add_registered_user,
    get_user,
    token_in_blocklist,
)
from src.exceptions import (
    ForbiddenError,
    InsufficientPermissionsError,
    NotFoundError,
    RoleChangedError,
    SessionRevokedError,
)

from .utils import decode_token, seconds_until_expiry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base cookie bearer
# ---------------------------------------------------------------------------


class CookieTokenBearer(SecurityBase):
    """
    Cookie-based JWT bearer.

    Inherits from SecurityBase (not HTTPBearer) so the OpenAPI schema is
    emitted as an `apiKey / in: cookie` entry instead of a misleading
    `http / bearer` header scheme. Swagger UI will correctly prompt for
    a cookie value rather than an Authorization header.
    """

    def __init__(self, cookie_name: str, auto_error: bool = True):
        self.cookie_name = cookie_name
        self.auto_error = auto_error
        # Tell OpenAPI exactly where the credential lives
        self.model = APIKey(
            **{"in": APIKeyIn.cookie},
            name=cookie_name,
            description=f"JWT stored in the `{cookie_name}` HttpOnly cookie",
        )
        self.scheme_name = self.__class__.__name__

    async def __call__(self, request: Request) -> dict | None:
        # If the middleware already rotated the token this request,
        # use the fresh token data directly — the cookie is stale.
        rotated = getattr(request.state, "rotated_token_data", None)
        if rotated is not None:
            self._verify_token_type(rotated)
            return rotated

        token = request.cookies.get(self.cookie_name)

        if not token:
            if not self.auto_error:
                return None
            raise ForbiddenError("No authentication cookie provided")

        token_data = decode_token(token)
        if token_data is None:
            # Token is expired or invalid. For optional-auth routes
            # (auto_error=False), treat as unauthenticated rather than
            # blocking — e.g. a public download shouldn't fail because
            # the browser sent a stale cookie.
            if not self.auto_error:
                return None
            raise ForbiddenError("Invalid or expired token")

        try:
            if await token_in_blocklist(token_data["jti"]):
                if not self.auto_error:
                    return None
                raise SessionRevokedError("This token has been revoked. Please log in again.")
        except SessionRevokedError:
            raise
        except Exception as e:
            # Redis is down — fail closed for the blocklist check because
            # allowing a revoked token through is a security hole.
            logger.error("Redis blocklist check failed — denying request", exc_info=True)
            if not self.auto_error:
                return None
            raise ForbiddenError("Authentication service temporarily unavailable") from e

        self._verify_token_type(token_data)

        # Backward-compat cross-check: tokens issued before the role-free
        # schema may still carry a "role" claim. If the live Redis role
        # differs, the user's role was changed — blocklist immediately and
        # force re-login.
        token_role = (token_data.get("user") or {}).get("role")
        if token_role is not None:
            try:
                live_role = await get_user(token_data["user"]["username"])
                if live_role is not None and live_role.value != token_role:
                    await add_jti_to_blocklist(token_data["jti"], seconds_until_expiry(token_data))
                    raise RoleChangedError()
            except RoleChangedError:
                raise
            except Exception:
                # Redis unavailable for role cross-check — skip gracefully.
                # The RoleChecker dependency will catch stale roles via DB
                # fallback on the next layer.
                logger.warning("Redis role cross-check failed — skipping", exc_info=True)

        return token_data

    def _verify_token_type(self, token_data: dict) -> None:
        raise NotImplementedError


class AccessTokenBearer(CookieTokenBearer):
    def __init__(self, auto_error: bool = True):
        super().__init__(cookie_name="access_token", auto_error=auto_error)

    def _verify_token_type(self, token_data: dict) -> None:
        if token_data.get("refresh"):
            raise ForbiddenError("Provide an access token, not a refresh token")


class RefreshTokenBearer(CookieTokenBearer):
    def __init__(self, auto_error: bool = True):
        super().__init__(cookie_name="refresh_token", auto_error=auto_error)

    def _verify_token_type(self, token_data: dict) -> None:
        if not token_data.get("refresh"):
            raise ForbiddenError("Provide a refresh token, not an access token")


# ---------------------------------------------------------------------------
# Role checker
# ---------------------------------------------------------------------------


class RoleChecker:
    """
    FastAPI dependency that verifies the caller has one of the allowed roles.

    Resolution order:
      1. Redis cache  (no DB hit on the hot path)
      2. PostgreSQL   (cache miss — also backfills Redis)

    Injects token_details into the route so user_id / username are available
    without a second Depends call.
    """

    def __init__(self, allowed_roles: list[MemberRoleEnum]) -> None:
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        token_details: dict = Depends(AccessTokenBearer()),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        username = token_details.get("user", {}).get("username")
        if not username:
            raise ForbiddenError("Invalid token payload")

        live_role = await self._resolve_role(username, session)

        if live_role is None:
            raise NotFoundError("User not found")

        if live_role not in self.allowed_roles:
            raise InsufficientPermissionsError()

        return token_details

    async def _resolve_role(self, username: str, session: AsyncSession) -> MemberRoleEnum | None:
        # Try Redis cache first
        try:
            role = await get_user(username)
            if role is not None:
                return role
        except Exception:
            # Redis unavailable — fall through to DB
            logger.warning("Redis cache miss (unavailable) for %s — falling back to DB", username)

        # Cache miss or Redis down — hit Postgres
        user: User | None = (
            await session.exec(select(User).where(User.username == username))
        ).first()
        if user is None:
            return None

        # Try to backfill the cache; don't crash if Redis is still down
        try:
            await add_registered_user(user.username, user.role)
        except Exception:
            logger.warning("Failed to backfill Redis cache for %s", username)

        return user.role


# ---------------------------------------------------------------------------
# Pre-built singletons
# ---------------------------------------------------------------------------

#: Any verified user (user, vip, or admin)
require_user = Depends(RoleChecker([MemberRoleEnum.USER, MemberRoleEnum.VIP, MemberRoleEnum.ADMIN]))

#: VIP or admin (e.g. file upload)
require_vip = Depends(RoleChecker([MemberRoleEnum.VIP, MemberRoleEnum.ADMIN]))

#: Admin only
require_admin = Depends(RoleChecker([MemberRoleEnum.ADMIN]))

#: Raw access token — for routes that handle their own logic (e.g. logout)
access_token_bearer = Depends(AccessTokenBearer())
