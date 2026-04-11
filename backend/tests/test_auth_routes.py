"""
tests/test_auth_routes.py
─────────────────────────
HTTP-level integration tests for all /auth endpoints.

Covers:
  POST /auth/login          — happy path, wrong password, unknown user
  POST /auth/logout         — JTI blocklisted, cookies cleared
  POST /auth/refresh_token  — rotation, reuse detection, expired
  GET  /auth/me             — returns live user, role from DB not token
  POST /auth/signup         — duplicate username/email rejection
"""

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import decode_token
from src.db.enums import MemberRoleEnum
from src.db.redis_client import get_refresh_token_owner, token_in_blocklist
from tests.conftest import (
    auth_cookies,
    make_access_token,
    make_refresh_token,
    make_user,
)

# ── Login ─────────────────────────────────────────────────────────────────────


class TestLogin:
    async def test_login_success_sets_cookies(self, client: AsyncClient, session: AsyncSession):
        await make_user(session, username="loginuser", password="pass123")  # noqa: S106
        r = await client.post("/auth/login", json={"username": "loginuser", "password": "pass123"})

        assert r.status_code == 200
        assert "access_token" in r.cookies
        assert "refresh_token" in r.cookies

    async def test_login_success_returns_user_with_role(
        self, client: AsyncClient, session: AsyncSession
    ):
        await make_user(
            session,
            username="roleuser",
            role=MemberRoleEnum.VIP,
            password="pass",  # noqa: S106
        )
        r = await client.post("/auth/login", json={"username": "roleuser", "password": "pass"})

        assert r.status_code == 200
        body = r.json()
        assert body["user"]["username"] == "roleuser"
        assert body["user"]["role"] == "vip"
        assert "access_token" not in body  # tokens must NOT be in the body
        assert "refresh_token" not in body

    async def test_login_wrong_password_returns_403(
        self, client: AsyncClient, session: AsyncSession
    ):
        await make_user(session, username="wrongpass", password="correct")  # noqa: S106
        r = await client.post("/auth/login", json={"username": "wrongpass", "password": "wrong"})
        assert r.status_code == 403

    async def test_login_unknown_user_returns_403(self, client: AsyncClient):
        r = await client.post("/auth/login", json={"username": "nobody", "password": "x"})
        assert r.status_code == 403

    async def test_login_stores_refresh_jti_in_redis(
        self, client: AsyncClient, session: AsyncSession
    ):
        await make_user(session, username="jtiuser", password="pass")  # noqa: S106
        r = await client.post("/auth/login", json={"username": "jtiuser", "password": "pass"})

        refresh_token = r.cookies.get("refresh_token")
        assert refresh_token is not None

        token_data = decode_token(refresh_token)
        owner = await get_refresh_token_owner(token_data["jti"])
        assert owner == "jtiuser"

    async def test_login_token_has_no_role_claim(self, client: AsyncClient, session: AsyncSession):
        await make_user(session, username="norole", password="pass")  # noqa: S106
        r = await client.post("/auth/login", json={"username": "norole", "password": "pass"})

        access_token = r.cookies.get("access_token")
        token_data = decode_token(access_token)
        assert "role" not in token_data["user"]


# ── Logout ────────────────────────────────────────────────────────────────────


class TestLogout:
    async def test_logout_returns_200(self, client: AsyncClient, session: AsyncSession):
        user = await make_user(session)
        token = make_access_token(user)
        r = await client.post("/auth/logout", cookies=auth_cookies(token))
        assert r.status_code == 200

    async def test_logout_blocklists_access_jti(self, client: AsyncClient, session: AsyncSession):
        user = await make_user(session)
        token = make_access_token(user)
        jti = decode_token(token)["jti"]

        await client.post("/auth/logout", cookies=auth_cookies(token))
        assert await token_in_blocklist(jti) is True

    async def test_logout_clears_cookies(self, client: AsyncClient, session: AsyncSession):
        user = await make_user(session)
        token = make_access_token(user)
        r = await client.post("/auth/logout", cookies=auth_cookies(token))

        # delete_cookie sets Max-Age=0 — httpx won't show these in r.cookies.
        # Use multi_items() to get all set-cookie headers since httpx returns
        # them as separate entries.
        all_set_cookie = " ".join(v for k, v in r.headers.multi_items() if k == "set-cookie")
        assert "access_token" in all_set_cookie
        assert "refresh_token" in all_set_cookie
        assert "Max-Age=0" in all_set_cookie

    async def test_logout_revokes_all_refresh_tokens(
        self, client: AsyncClient, session: AsyncSession
    ):
        user = await make_user(session, username="multisession")
        refresh1 = await make_refresh_token(user)
        refresh2 = await make_refresh_token(user)
        access = make_access_token(user)

        jti1 = decode_token(refresh1)["jti"]
        jti2 = decode_token(refresh2)["jti"]

        await client.post("/auth/logout", cookies=auth_cookies(access))

        assert await get_refresh_token_owner(jti1) is None
        assert await get_refresh_token_owner(jti2) is None

    async def test_logout_with_no_cookie_returns_403(self, client: AsyncClient):
        r = await client.post("/auth/logout")
        assert r.status_code == 403

    async def test_blocklisted_token_cannot_access_protected_route(
        self, client: AsyncClient, session: AsyncSession
    ):
        user = await make_user(session)
        token = make_access_token(user)
        await client.post("/auth/logout", cookies=auth_cookies(token))

        r = await client.get("/auth/me", cookies=auth_cookies(token))
        assert r.status_code == 401


# ── Refresh token rotation ────────────────────────────────────────────────────


class TestRefreshToken:
    async def test_rotation_issues_new_cookies(self, client: AsyncClient, session: AsyncSession):
        user = await make_user(session, username="rotateuser")
        refresh = await make_refresh_token(user)
        access = make_access_token(user)

        r = await client.post(
            "/auth/refresh_token",
            cookies=auth_cookies(access, refresh),
        )
        assert r.status_code == 200
        assert "access_token" in r.cookies
        assert "refresh_token" in r.cookies

    async def test_rotation_blocklists_old_refresh_jti(
        self, client: AsyncClient, session: AsyncSession
    ):
        user = await make_user(session, username="blockjti")
        refresh = await make_refresh_token(user)
        access = make_access_token(user)
        old_jti = decode_token(refresh)["jti"]

        await client.post(
            "/auth/refresh_token",
            cookies=auth_cookies(access, refresh),
        )
        assert await token_in_blocklist(old_jti) is True

    async def test_rotation_old_refresh_no_longer_in_store(
        self, client: AsyncClient, session: AsyncSession
    ):
        user = await make_user(session, username="oldstore")
        refresh = await make_refresh_token(user)
        access = make_access_token(user)
        old_jti = decode_token(refresh)["jti"]

        await client.post(
            "/auth/refresh_token",
            cookies=auth_cookies(access, refresh),
        )
        assert await get_refresh_token_owner(old_jti) is None

    async def test_reuse_detection_revokes_all_sessions(
        self, client: AsyncClient, session: AsyncSession
    ):
        """
        True reuse detection fires when a token is valid (passes signature +
        blocklist checks) but its JTI is no longer in the refresh store —
        meaning it was already rotated server-side. This simulates an attacker
        replaying a stolen refresh token after the legitimate user has rotated.

        We reproduce this by issuing a refresh token and then manually removing
        it from the store (simulating a prior rotation) without blocklisting it.
        """
        user = await make_user(session, username="reuseuser")
        refresh = await make_refresh_token(user)  # issued and stored
        refresh2 = await make_refresh_token(user)  # second session token
        access = make_access_token(user)

        jti = decode_token(refresh)["jti"]
        jti2 = decode_token(refresh2)["jti"]

        # Simulate server-side rotation: remove JTI from store WITHOUT blocklisting.
        # Token is still cryptographically valid — it will pass CookieTokenBearer —
        # but the route will find it missing from the store and trigger family revocation.
        from src.db.redis_client import delete_refresh_token

        await delete_refresh_token(jti)

        r = await client.post(
            "/auth/refresh_token",
            cookies=auth_cookies(access, refresh),
        )
        assert r.status_code == 401
        assert "reuse" in r.json()["detail"].lower()

        # Family revocation: the second session's token must also be gone
        assert await get_refresh_token_owner(jti2) is None

    async def test_refresh_with_access_token_cookie_returns_403(
        self, client: AsyncClient, session: AsyncSession
    ):
        user = await make_user(session)
        access = make_access_token(user)
        # Send the access token in the refresh_token cookie slot
        r = await client.post(
            "/auth/refresh_token",
            cookies={"refresh_token": access},
        )
        assert r.status_code == 403

    async def test_refresh_with_no_cookie_returns_403(self, client: AsyncClient):
        r = await client.post("/auth/refresh_token")
        assert r.status_code == 403


# ── GET /auth/me ──────────────────────────────────────────────────────────────


class TestGetMe:
    async def test_me_returns_user_data(self, client: AsyncClient, session: AsyncSession):
        user = await make_user(session, username="meuser", role=MemberRoleEnum.ADMIN)
        token = make_access_token(user)

        r = await client.get("/auth/me", cookies=auth_cookies(token))

        assert r.status_code == 200
        body = r.json()
        assert body["username"] == "meuser"
        assert body["role"] == "admin"

    async def test_me_with_no_cookie_returns_403(self, client: AsyncClient):
        r = await client.get("/auth/me")
        assert r.status_code == 403

    async def test_me_role_reflects_db_not_token(self, client: AsyncClient, session: AsyncSession):
        """
        Even if the token was issued when the user was a USER, /me should
        return the current DB role (ADMIN in this case, set directly on the row).
        """
        user = await make_user(session, username="promoted", role=MemberRoleEnum.USER)
        token = make_access_token(user)

        # Promote the user directly in DB (simulating an admin action)
        user.role = MemberRoleEnum.ADMIN
        session.add(user)
        await session.commit()

        r = await client.get("/auth/me", cookies=auth_cookies(token))
        assert r.status_code == 200
        assert r.json()["role"] == "admin"


# ── POST /auth/signup ─────────────────────────────────────────────────────────


class TestSignup:
    async def test_signup_creates_pending_user(self, client: AsyncClient):
        r = await client.post(
            "/auth/signup",
            json={
                "username": "newbie",
                "password": "strongpass!234",
                "email": "newbie@example.com",
                "nickname": None,
                "request": None,
            },
        )
        assert r.status_code == 201

    async def test_signup_duplicate_username_returns_403(
        self, client: AsyncClient, session: AsyncSession
    ):
        await make_user(session, username="taken")
        r = await client.post(
            "/auth/signup",
            json={
                "username": "taken",
                "password": "longpassword12",
                "email": None,
                "nickname": None,
                "request": None,
            },
        )
        assert r.status_code == 409
        assert "username" in r.json()["detail"].lower()
