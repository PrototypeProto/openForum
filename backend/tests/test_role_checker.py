"""
tests/test_role_checker.py
──────────────────────────
Tests for CookieTokenBearer and RoleChecker at the dependency level.
These use the HTTP client so the full FastAPI dependency chain fires,
but the routes tested are auth/me and forum/groups which are simple
enough to serve as clean probes.

Covers:
  CookieTokenBearer  — missing cookie, blocklisted JTI, refresh in access slot,
                       stale role claim revocation
  RoleChecker        — redis cache hit, DB fallback + backfill,
                       wrong role, user not in DB
"""

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.schemas import AccessTokenUserData
from src.auth.utils import create_access_token, decode_token
from src.db.enums import MemberRoleEnum
from src.db.redis_client import (
    add_jti_to_blocklist,
    add_registered_user,
    get_user,
    token_in_blocklist,
)
from tests.conftest import auth_cookies, make_access_token, make_user

# ── CookieTokenBearer ─────────────────────────────────────────────────────────


class TestCookieTokenBearer:
    async def test_missing_cookie_returns_403(self, client: AsyncClient):
        r = await client.get("/auth/me")
        assert r.status_code == 403
        assert "cookie" in r.json()["detail"].lower()

    async def test_garbage_cookie_returns_403(self, client: AsyncClient):
        r = await client.get("/auth/me", cookies={"access_token": "not.a.jwt"})
        assert r.status_code == 403

    async def test_blocklisted_jti_returns_403(self, client: AsyncClient, session: AsyncSession):
        user = await make_user(session)
        token = make_access_token(user)
        jti = decode_token(token)["jti"]
        await add_jti_to_blocklist(jti, ttl_seconds=300)

        r = await client.get("/auth/me", cookies=auth_cookies(token))
        assert r.status_code == 401
        body = r.json()
        assert body["error"] == "session_revoked"
        assert "revoked" in body["detail"].lower()

    async def test_refresh_token_in_access_slot_returns_403(
        self, client: AsyncClient, session: AsyncSession
    ):
        user = await make_user(session)
        from tests.conftest import make_refresh_token

        refresh = await make_refresh_token(user)

        # Send the refresh token where the access token is expected
        r = await client.get("/auth/me", cookies={"access_token": refresh})
        assert r.status_code == 403
        assert "access token" in r.json()["detail"].lower()

    async def test_stale_role_claim_is_blocklisted_and_returns_401(
        self, client: AsyncClient, session: AsyncSession
    ):
        """
        Tokens issued before the role-free schema carried a role claim.
        If that claim doesn't match the live Redis role, the JTI must be
        blocklisted and a 401 returned.
        """
        user = await make_user(session, username="staleclaim", role=MemberRoleEnum.USER)

        # Manually craft a token with a stale role claim
        data = AccessTokenUserData(
            user_id=str(user.user_id),
            username=user.username,
            nickname=user.nickname,
        ).model_dump()
        data["role"] = "user"  # inject old-style role claim
        stale_token = create_access_token(user_data=data)
        jti = decode_token(stale_token)["jti"]

        # Set a *different* live role in Redis to trigger the mismatch
        await add_registered_user(user.username, MemberRoleEnum.ADMIN)

        r = await client.get("/auth/me", cookies={"access_token": stale_token})
        assert r.status_code == 401
        assert "role change" in r.json()["detail"].lower()

        # JTI must be blocklisted so the token can never be reused
        assert await token_in_blocklist(jti) is True

    async def test_valid_token_with_no_role_claim_passes(
        self, client: AsyncClient, session: AsyncSession
    ):
        """Normal new-style tokens (no role claim) must pass through cleanly."""
        user = await make_user(session, username="norole")
        token = make_access_token(user)

        # Confirm the token really has no role
        assert "role" not in decode_token(token)["user"]

        # Prime Redis so RoleChecker can resolve the user
        await add_registered_user(user.username, MemberRoleEnum.USER)

        r = await client.get("/auth/me", cookies=auth_cookies(token))
        assert r.status_code == 200


# ── RoleChecker ───────────────────────────────────────────────────────────────


class TestRoleChecker:
    async def test_redis_cache_hit_allows_access(self, client: AsyncClient, session: AsyncSession):
        """Role resolved from Redis cache — no DB hit needed."""
        user = await make_user(session, username="cached", role=MemberRoleEnum.USER)
        token = make_access_token(user)
        await add_registered_user(user.username, MemberRoleEnum.USER)

        r = await client.get("/auth/me", cookies=auth_cookies(token))
        assert r.status_code == 200

    async def test_db_fallback_backfills_redis(self, client: AsyncClient, session: AsyncSession):
        """
        On a cold Redis cache, RoleChecker must query the DB and then write
        the role back into Redis so the next request is a cache hit.
        """
        user = await make_user(session, username="coldcache", role=MemberRoleEnum.VIP)
        token = make_access_token(user)

        # Do NOT prime Redis — cache is cold
        assert await get_user(user.username) is None

        r = await client.get("/auth/me", cookies=auth_cookies(token))
        assert r.status_code == 200

        # Redis must now have the role
        cached_role = await get_user(user.username)
        assert cached_role == MemberRoleEnum.VIP

    async def test_wrong_role_returns_403(self, client: AsyncClient, session: AsyncSession):
        """A USER cannot access an admin-only endpoint."""
        user = await make_user(session, username="notadmin", role=MemberRoleEnum.USER)
        token = make_access_token(user)
        await add_registered_user(user.username, MemberRoleEnum.USER)

        r = await client.get("/admin/users", cookies=auth_cookies(token))
        assert r.status_code == 403
        assert "permissions" in r.json()["detail"].lower()

    async def test_admin_can_access_admin_route(self, client: AsyncClient, session: AsyncSession):
        user = await make_user(session, username="isadmin", role=MemberRoleEnum.ADMIN)
        token = make_access_token(user)
        await add_registered_user(user.username, MemberRoleEnum.ADMIN)

        r = await client.get("/admin/users", cookies=auth_cookies(token))
        assert r.status_code == 200

    async def test_vip_cannot_access_admin_route(self, client: AsyncClient, session: AsyncSession):
        user = await make_user(session, username="vipuser", role=MemberRoleEnum.VIP)
        token = make_access_token(user)
        await add_registered_user(user.username, MemberRoleEnum.VIP)

        r = await client.get("/admin/users", cookies=auth_cookies(token))
        assert r.status_code == 403

    async def test_vip_can_access_user_route(self, client: AsyncClient, session: AsyncSession):
        """VIP is a superset of USER — must be allowed on require_user routes."""
        user = await make_user(session, username="viponforum", role=MemberRoleEnum.VIP)
        token = make_access_token(user)
        await add_registered_user(user.username, MemberRoleEnum.VIP)

        r = await client.get("/forum/groups", cookies=auth_cookies(token))
        assert r.status_code == 200

    async def test_user_not_in_db_returns_403(self, client: AsyncClient):
        """
        A token that decodes successfully but references a username that
        doesn't exist in the DB (and isn't in Redis) must be rejected.
        """
        phantom_data = {
            "user_id": "00000000-0000-0000-0000-000000000000",
            "username": "phantom_user",
            "nickname": None,
        }
        token = create_access_token(user_data=phantom_data)

        r = await client.get("/auth/me", cookies=auth_cookies(token))
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()

    async def test_role_change_immediately_enforced(
        self, client: AsyncClient, session: AsyncSession
    ):
        """
        After update_user_role writes the new role to Redis, the next request
        with an old (role-free) token must see the new role and either allow
        or deny accordingly.

        Here: a USER is promoted to ADMIN — their existing token must gain
        admin access on the very next request (because RoleChecker reads the
        live Redis role, not the token).
        """
        user = await make_user(session, username="promoted", role=MemberRoleEnum.USER)
        token = make_access_token(user)
        await add_registered_user(user.username, MemberRoleEnum.USER)

        # Currently USER — admin route must be blocked
        r1 = await client.get("/admin/users", cookies=auth_cookies(token))
        assert r1.status_code == 403

        # Promote in Redis (simulating what update_user_role does)
        await add_registered_user(user.username, MemberRoleEnum.ADMIN)
        user.role = MemberRoleEnum.ADMIN
        session.add(user)
        await session.commit()

        # Same token — now ADMIN
        r2 = await client.get("/admin/users", cookies=auth_cookies(token))
        assert r2.status_code == 200
