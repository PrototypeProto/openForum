"""
tests/test_csrf.py
──────────────────
Tests for the CSRF double-submit cookie implementation.

Two tiers:

  Pure unit tests — generate_csrf_token, set_csrf_cookie, delete_csrf_cookie
    Verify the token generator and cookie helpers without HTTP.

  Integration tests — verify_csrf_token via real HTTP endpoints
    Use the test client to confirm that mutating routes enforce the
    double-submit check in non-testing environments, and that the
    CSRF cookie is correctly issued on login/refresh and cleared on logout.

NOTE: verify_csrf_token short-circuits when Config.is_testing is True
(ENVIRONMENT=testing in .env.test), so the enforcement tests temporarily
override Config.is_testing to False to exercise the actual check logic.
"""

import secrets
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.csrf import (
    _CSRF_COOKIE_NAME_HOST,
    _CSRF_COOKIE_NAME_PLAIN,
    CSRF_TOKEN_BYTES,
    _csrf_cookie_name,
    generate_csrf_token,
)
from src.config import Config
from src.db.models import Topic, TopicGroup
from tests.conftest import auth_cookies, make_access_token, make_user
from tests.constants import TEST_BODY, TEST_TITLE

# In testing, Config.cookie_secure=False so plain name is used
CSRF_COOKIE_NAME = _csrf_cookie_name()
# ══════════════════════════════════════════════════════════════════════════════
# Pure unit tests — token generator and cookie shape
# ══════════════════════════════════════════════════════════════════════════════


class TestGenerateCsrfToken:
    def test_returns_hex_string(self):
        token = generate_csrf_token()
        assert isinstance(token, str)
        # Hex string: only 0-9 a-f
        assert all(c in "0123456789abcdef" for c in token)

    def test_correct_length(self):
        # CSRF_TOKEN_BYTES bytes → 2 hex chars per byte
        token = generate_csrf_token()
        assert len(token) == CSRF_TOKEN_BYTES * 2

    def test_each_call_returns_different_token(self):
        tokens = {generate_csrf_token() for _ in range(20)}
        assert len(tokens) == 20  # all distinct (astronomically unlikely to collide)

    def test_constant_time_comparison_works(self):
        """secrets.compare_digest must accept two equal tokens."""
        token = generate_csrf_token()
        assert secrets.compare_digest(token, token) is True

    def test_constant_time_comparison_rejects_mismatch(self):
        t1 = generate_csrf_token()
        t2 = generate_csrf_token()
        # Two random tokens must differ (extremely high probability)
        assert secrets.compare_digest(t1, t2) is False


# ══════════════════════════════════════════════════════════════════════════════
# Login sets CSRF cookie, logout clears it, refresh rotates it
# ══════════════════════════════════════════════════════════════════════════════


class TestCsrfCookieNameSelection:
    def test_plain_name_in_development(self, monkeypatch):
        """Non-HTTPS environments use the plain cookie name."""
        # Patch the underlying field, not the computed property (which has no setter).
        # cookie_secure derives from ENVIRONMENT so setting ENVIRONMENT is the right lever.
        monkeypatch.setattr(Config, "ENVIRONMENT", "development")
        assert _csrf_cookie_name() == _CSRF_COOKIE_NAME_PLAIN

    def test_host_prefix_in_production(self, monkeypatch):
        """HTTPS environments use __Host- prefixed name to block subdomain injection."""
        monkeypatch.setattr(Config, "ENVIRONMENT", "production")
        assert _csrf_cookie_name() == _CSRF_COOKIE_NAME_HOST

    def test_host_prefix_starts_with_dunder_host(self):
        assert _CSRF_COOKIE_NAME_HOST.startswith("__Host-")

    def test_plain_name_has_no_prefix(self):
        assert not _CSRF_COOKIE_NAME_PLAIN.startswith("__")


class TestCsrfCookieLifecycle:
    async def test_login_sets_csrf_cookie(self, client: AsyncClient, session: AsyncSession):
        await make_user(session, username="csrflogin")
        r = await client.post(
            "/auth/login", json={"username": "csrflogin", "password": "testpassword1"}
        )
        assert r.status_code == 200
        assert CSRF_COOKIE_NAME in r.cookies

    async def test_csrf_cookie_is_not_httponly(self, client: AsyncClient, session: AsyncSession):
        """
        The csrf_token cookie must NOT be HttpOnly — JavaScript needs to read
        it to copy it into the X-CSRF-Token header.
        """
        await make_user(session, username="csrfhttponly")
        r = await client.post(
            "/auth/login",
            json={"username": "csrfhttponly", "password": "testpassword1"},
        )
        set_cookie_headers = [
            v for k, v in r.headers.multi_items() if k == "set-cookie" and CSRF_COOKIE_NAME in v
        ]
        assert set_cookie_headers, "csrf_token set-cookie header not found"
        header = set_cookie_headers[0].lower()
        assert "httponly" not in header, "csrf_token must NOT be HttpOnly"

    async def test_logout_clears_csrf_cookie(self, client: AsyncClient, session: AsyncSession):
        user = await make_user(session, username="csrflogout")
        token = make_access_token(user)

        r = await client.post("/auth/logout", cookies=auth_cookies(token))

        set_cookie = " ".join(v for k, v in r.headers.multi_items() if k == "set-cookie")
        assert CSRF_COOKIE_NAME in set_cookie
        assert "Max-Age=0" in set_cookie

    async def test_refresh_issues_new_csrf_cookie(self, client: AsyncClient, session: AsyncSession):
        from tests.conftest import make_refresh_token

        user = await make_user(session, username="csrfrefresh")

        # Login to get initial CSRF token
        r_login = await client.post(
            "/auth/login",
            json={"username": "csrfrefresh", "password": "testpassword1"},
        )
        initial_csrf = r_login.cookies.get(CSRF_COOKIE_NAME)
        assert initial_csrf

        # Refresh — must set a new (different) CSRF token
        refresh = await make_refresh_token(user)
        access = make_access_token(user)
        r_refresh = await client.post(
            "/auth/refresh_token",
            cookies={**auth_cookies(access, refresh), CSRF_COOKIE_NAME: initial_csrf},
        )
        assert r_refresh.status_code == 200
        assert CSRF_COOKIE_NAME in r_refresh.cookies
        new_csrf = r_refresh.cookies[CSRF_COOKIE_NAME]
        # Each rotation issues a fresh token
        assert new_csrf != initial_csrf


# ══════════════════════════════════════════════════════════════════════════════
# verify_csrf_token enforcement (override is_testing so the check fires)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def enforce_csrf(monkeypatch):
    """
    Temporarily make verify_csrf_token run the double-submit check by
    presenting it with a Config whose is_testing=False and cookie_secure=False.

    We cannot monkeypatch.setattr(Config, "is_testing", ...) because
    is_testing is a @property on a pydantic BaseSettings instance — pydantic
    intercepts __setattr__ and raises AttributeError for read-only descriptors.

    Instead we patch the Config *reference* inside src.auth.csrf with a
    SimpleNamespace that has the exact attributes csrf.py reads. This is
    precise: only csrf.py sees the fake config; the rest of the app is unaffected.
    """
    import types

    import src.auth.csrf as csrf_module

    fake_config = types.SimpleNamespace(
        is_testing=False,
        cookie_secure=False,  # keeps plain cookie name (no __Host- in tests)
        cookie_samesite="lax",
    )
    monkeypatch.setattr(csrf_module, "Config", fake_config)
    yield


class TestVerifyCsrfTokenEnforcement:
    async def test_missing_header_returns_403(
        self, client: AsyncClient, session: AsyncSession, enforce_csrf
    ):
        from src.db.enums import MemberRoleEnum
        from src.db.redis_client import add_registered_user

        user = await make_user(session, username="nohdrcsrf")
        await add_registered_user(user.username, MemberRoleEnum.USER)
        token = make_access_token(user)
        topic_group = await _make_topic_group(session)
        topic = await _make_topic(session, group_id=topic_group.group_id)

        csrf_token = generate_csrf_token()
        r = await client.post(
            f"/forum/topics/{topic.topic_id}/threads",
            json={"title": TEST_TITLE, "body": TEST_BODY},
            # CSRF cookie present but header absent
            cookies={**auth_cookies(token), CSRF_COOKIE_NAME: csrf_token},
        )
        assert r.status_code == 403
        assert "csrf" in r.json()["detail"].lower()

    async def test_missing_cookie_returns_403(
        self, client: AsyncClient, session: AsyncSession, enforce_csrf
    ):
        from src.db.enums import MemberRoleEnum
        from src.db.redis_client import add_registered_user

        user = await make_user(session, username="nocookiecsrf")
        await add_registered_user(user.username, MemberRoleEnum.USER)
        token = make_access_token(user)
        topic_group = await _make_topic_group(session)
        topic = await _make_topic(session, group_id=topic_group.group_id)

        csrf_token = generate_csrf_token()
        r = await client.post(
            f"/forum/topics/{topic.topic_id}/threads",
            json={"title": TEST_TITLE, "body": TEST_BODY},
            # Header present but CSRF cookie absent
            headers={"X-CSRF-Token": csrf_token},
            cookies=auth_cookies(token),
        )
        assert r.status_code == 403
        assert "csrf" in r.json()["detail"].lower()

    async def test_mismatched_tokens_returns_403(
        self, client: AsyncClient, session: AsyncSession, enforce_csrf
    ):
        from src.db.enums import MemberRoleEnum
        from src.db.redis_client import add_registered_user

        user = await make_user(session, username="mismatchcsrf")
        await add_registered_user(user.username, MemberRoleEnum.USER)
        token = make_access_token(user)
        topic_group = await _make_topic_group(session)
        topic = await _make_topic(session, group_id=topic_group.group_id)

        r = await client.post(
            f"/forum/topics/{topic.topic_id}/threads",
            json={"title": TEST_TITLE, "body": TEST_BODY},
            headers={"X-CSRF-Token": generate_csrf_token()},
            cookies={**auth_cookies(token), CSRF_COOKIE_NAME: generate_csrf_token()},
        )
        assert r.status_code == 403
        assert "csrf" in r.json()["detail"].lower()

    async def test_matching_tokens_allows_request(
        self, client: AsyncClient, session: AsyncSession, enforce_csrf
    ):
        from src.db.enums import MemberRoleEnum
        from src.db.redis_client import add_registered_user

        user = await make_user(session, username="matchcsrf")
        await add_registered_user(user.username, MemberRoleEnum.USER)
        token = make_access_token(user)
        topic_group = await _make_topic_group(session)
        topic = await _make_topic(session, group_id=topic_group.group_id)

        csrf_token = generate_csrf_token()
        r = await client.post(
            f"/forum/topics/{topic.topic_id}/threads",
            json={"title": TEST_TITLE, "body": TEST_BODY},
            headers={"X-CSRF-Token": csrf_token},
            cookies={**auth_cookies(token), CSRF_COOKIE_NAME: csrf_token},
        )
        # 201 = CSRF passed, request processed
        assert r.status_code == 201


# ══════════════════════════════════════════════════════════════════════════════
# Helpers (local factories — not worth putting in conftest)
# ══════════════════════════════════════════════════════════════════════════════


async def _make_topic_group(session: AsyncSession) -> TopicGroup:
    g = TopicGroup(name=f"g_{uuid4().hex[:6]}", display_order=0)
    session.add(g)
    await session.commit()
    await session.refresh(g)
    return g


async def _make_topic(session: AsyncSession, *, group_id) -> Topic:
    t = Topic(
        group_id=group_id,
        name=f"t_{uuid4().hex[:6]}",
        display_order=0,
        thread_count=0,
        reply_count=0,
    )
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t
