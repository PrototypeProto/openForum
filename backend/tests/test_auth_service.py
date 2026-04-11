"""
tests/test_auth_service.py
──────────────────────────
Service-layer unit tests for AuthService.

These call the singleton directly with the test session — no HTTP, no router,
no middleware. Each test exercises a specific method or branch of business
logic that integration tests only hit indirectly.

Covers:
  username_exists      — VALID, PENDING, DNE
  email_exists         — VALID, PENDING, DNE
  get_user_with_*      — hit and miss
  register_user        — creates PendingUser row + hashed password
  is_valid_user_token  — Redis cache hit, DB fallback, invalid token shapes
  generate_tokens      — access + refresh issued, refresh JTI stored in Redis
"""

from datetime import date

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.schemas import LoginResultEnum
from src.auth.utils import decode_token, generate_passwd_hash, verify_passwd
from src.db.enums import MemberRoleEnum
from src.db.models import PendingUser, UserID
from src.db.redis_client import add_registered_user, get_refresh_token_owner
from src.db.schemas import RegisterUserModel
from tests.conftest import make_user
from tests.constants import (
    TEST_PASSWORD,
    TEST_PASSWORD_ALT,
    TEST_PASSWORD_STUB,
)


# ── username_exists ────────────────────────────────────────────────────────────


class TestUsernameExists:
    async def test_returns_valid_for_verified_user(
        self, auth_svc, session: AsyncSession
    ):
        await make_user(session, username="verifieduser")
        result = await auth_svc.username_exists("verifieduser", session)
        assert result == LoginResultEnum.VALID

    async def test_returns_pending_for_pending_user(
        self, auth_svc, session: AsyncSession
    ):
        uid = UserID()
        session.add(uid)
        await session.commit()
        await session.refresh(uid)

        pending = PendingUser(
            user_id=uid.id,
            username="pendingonly",
            email=None,
            password_hash=generate_passwd_hash(TEST_PASSWORD_STUB),
            join_date=date.today(),
        )
        session.add(pending)
        await session.commit()

        result = await auth_svc.username_exists("pendingonly", session)
        assert result == LoginResultEnum.PENDING

    async def test_returns_dne_for_unknown_user(self, auth_svc, session: AsyncSession):
        result = await auth_svc.username_exists("ghostuser", session)
        assert result == LoginResultEnum.DNE


# ── email_exists ───────────────────────────────────────────────────────────────


class TestEmailExists:
    async def test_returns_valid_for_verified_email(
        self, auth_svc, session: AsyncSession
    ):
        await make_user(session, username="emailverified")
        # make_user doesn't set email, so insert one directly
        user = await auth_svc.get_user_with_username("emailverified", session)
        user.email = "verified@example.com"
        session.add(user)
        await session.commit()

        result = await auth_svc.email_exists("verified@example.com", session)
        assert result == LoginResultEnum.VALID

    async def test_returns_pending_for_pending_email(
        self, auth_svc, session: AsyncSession
    ):
        uid = UserID()
        session.add(uid)
        await session.commit()
        await session.refresh(uid)

        pending = PendingUser(
            user_id=uid.id,
            username="pendingemail",
            email="pending@example.com",
            password_hash=generate_passwd_hash(TEST_PASSWORD_STUB),
            join_date=date.today(),
        )
        session.add(pending)
        await session.commit()

        result = await auth_svc.email_exists("pending@example.com", session)
        assert result == LoginResultEnum.PENDING

    async def test_returns_dne_for_unknown_email(self, auth_svc, session: AsyncSession):
        result = await auth_svc.email_exists("nobody@example.com", session)
        assert result == LoginResultEnum.DNE


# ── get_user_with_username / get_user_with_email ───────────────────────────────


class TestUserLookups:
    async def test_get_user_with_username_hit(self, auth_svc, session: AsyncSession):
        await make_user(session, username="lookmeup")
        user = await auth_svc.get_user_with_username("lookmeup", session)
        assert user is not None
        assert user.username == "lookmeup"

    async def test_get_user_with_username_miss(self, auth_svc, session: AsyncSession):
        user = await auth_svc.get_user_with_username("doesnotexist", session)
        assert user is None

    async def test_get_pending_user_with_username_hit(
        self, auth_svc, session: AsyncSession
    ):
        uid = UserID()
        session.add(uid)
        await session.commit()
        await session.refresh(uid)

        pending = PendingUser(
            user_id=uid.id,
            username="findpending",
            email=None,
            password_hash=generate_passwd_hash(TEST_PASSWORD_STUB),
            join_date=date.today(),
        )
        session.add(pending)
        await session.commit()

        found = await auth_svc.get_pending_user_with_username("findpending", session)
        assert found is not None
        assert found.username == "findpending"

    async def test_get_pending_user_with_username_miss(
        self, auth_svc, session: AsyncSession
    ):
        found = await auth_svc.get_pending_user_with_username("nopending", session)
        assert found is None


# ── register_user ──────────────────────────────────────────────────────────────


class TestRegisterUser:
    async def test_creates_pending_user_row(self, auth_svc, session: AsyncSession):
        payload = RegisterUserModel(
            username="newpending",
            password=TEST_PASSWORD,
            email=None,
            nickname=None,
            request=None,
        )
        result = await auth_svc.register_user(payload, session)

        assert result.username == "newpending"
        # Verify it landed in the DB as a pending user
        found = await auth_svc.get_pending_user_with_username("newpending", session)
        assert found is not None

    async def test_password_is_hashed_not_plaintext(
        self, auth_svc, session: AsyncSession
    ):
        payload = RegisterUserModel(
            username="hashcheck",
            password=TEST_PASSWORD_ALT,
            email=None,
            nickname=None,
            request=None,
        )
        result = await auth_svc.register_user(payload, session)

        assert result.password_hash != TEST_PASSWORD_ALT
        assert verify_passwd(TEST_PASSWORD_ALT, result.password_hash)

    async def test_join_date_set_to_today(self, auth_svc, session: AsyncSession):
        payload = RegisterUserModel(
            username="datecheck",
            password=TEST_PASSWORD,
            email=None,
            nickname=None,
            request=None,
        )
        result = await auth_svc.register_user(payload, session)
        assert result.join_date == date.today()


# ── generate_tokens ────────────────────────────────────────────────────────────


class TestGenerateTokens:
    async def test_returns_two_tokens(self, auth_svc, session: AsyncSession):
        user = await make_user(session, username="tokenuser")
        access, refresh = await auth_svc.generate_tokens(user)
        assert access
        assert refresh
        assert access != refresh

    async def test_access_token_not_refresh(self, auth_svc, session: AsyncSession):
        user = await make_user(session, username="accesstype")
        access, _ = await auth_svc.generate_tokens(user)
        data = decode_token(access)
        assert data is not None
        assert not data.get("refresh")

    async def test_refresh_token_is_refresh(self, auth_svc, session: AsyncSession):
        user = await make_user(session, username="refreshtype")
        _, refresh = await auth_svc.generate_tokens(user)
        data = decode_token(refresh)
        assert data is not None
        assert data.get("refresh") is True

    async def test_refresh_jti_stored_in_redis(self, auth_svc, session: AsyncSession):
        user = await make_user(session, username="jtistore")
        _, refresh = await auth_svc.generate_tokens(user)
        jti = decode_token(refresh)["jti"]
        owner = await get_refresh_token_owner(jti)
        assert owner == "jtistore"

    async def test_token_payload_contains_user_data(
        self, auth_svc, session: AsyncSession
    ):
        user = await make_user(session, username="payloadcheck")
        access, _ = await auth_svc.generate_tokens(user)
        data = decode_token(access)
        assert data["user"]["username"] == "payloadcheck"
        assert "user_id" in data["user"]

    async def test_token_payload_has_no_role(self, auth_svc, session: AsyncSession):
        """Role must never be embedded in the token — it is resolved live."""
        user = await make_user(session, username="noroletoken", role=MemberRoleEnum.ADMIN)
        access, _ = await auth_svc.generate_tokens(user)
        data = decode_token(access)
        assert "role" not in data["user"]


# ── is_valid_user_token ────────────────────────────────────────────────────────


class TestIsValidUserToken:
    async def test_redis_cache_hit_returns_true(self, auth_svc, session: AsyncSession):
        user = await make_user(session, username="cachedhit")
        await add_registered_user(user.username, MemberRoleEnum.USER)

        token_details = {"user": {"username": "cachedhit", "user_id": str(user.user_id)}}
        assert await auth_svc.is_valid_user_token(token_details, session) is True

    async def test_db_fallback_returns_true_and_backfills(
        self, auth_svc, session: AsyncSession
    ):
        """Redis miss → DB hit → backfill cache → return True."""
        from src.db.redis_client import get_user

        user = await make_user(session, username="dbfallback")
        # Deliberately do NOT prime Redis

        token_details = {"user": {"username": "dbfallback", "user_id": str(user.user_id)}}
        result = await auth_svc.is_valid_user_token(token_details, session)
        assert result is True

        # Cache should now be backfilled
        cached_role = await get_user("dbfallback")
        assert cached_role is not None

    async def test_unknown_user_returns_false(self, auth_svc, session: AsyncSession):
        token_details = {"user": {"username": "phantom", "user_id": "some-id"}}
        assert await auth_svc.is_valid_user_token(token_details, session) is False

    async def test_none_token_details_returns_false(
        self, auth_svc, session: AsyncSession
    ):
        assert await auth_svc.is_valid_user_token(None, session) is False

    async def test_empty_dict_returns_false(self, auth_svc, session: AsyncSession):
        assert await auth_svc.is_valid_user_token({}, session) is False

    async def test_missing_username_key_returns_false(
        self, auth_svc, session: AsyncSession
    ):
        assert await auth_svc.is_valid_user_token({"user": {}}, session) is False
