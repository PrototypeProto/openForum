"""
tests/test_admin_routes.py
──────────────────────────
Integration tests for all /admin endpoints.

Covers:
  GET  /admin/users           — lists verified users, non-admin blocked
  GET  /admin/users/pending   — lists pending users
  GET  /admin/users/stats     — returns user counts
  PATCH /admin/users/{u}/role — updates role, invalidates Redis cache
  POST /admin/users/{u}/approve — pending → verified
  POST /admin/users/{u}/reject  — pending → rejected
"""

from datetime import date

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import generate_passwd_hash
from src.db.enums import MemberRoleEnum
from src.db.models import PendingUser, UserID
from src.db.redis_client import add_registered_user, get_user
from tests.conftest import auth_cookies, make_access_token, make_user
from tests.constants import TEST_PASSWORD_STUB, TEST_PENDING_REQUEST

# ── Helpers ───────────────────────────────────────────────────────────────────


async def make_pending_user(
    session: AsyncSession,
    *,
    username: str = None,
    password: str = TEST_PASSWORD_STUB,
) -> PendingUser:
    """Insert a PendingUser row directly, bypassing the signup endpoint."""
    from uuid import uuid4

    username = username or f"pending_{uuid4().hex[:6]}"

    uid = UserID()
    session.add(uid)
    await session.commit()
    await session.refresh(uid)

    pending = PendingUser(
        user_id=uid.id,
        username=username,
        email=f"{username}@example.com",
        password_hash=generate_passwd_hash(password),
        nickname=None,
        join_date=date.today(),
        request=TEST_PENDING_REQUEST,
    )
    session.add(pending)
    await session.commit()
    await session.refresh(pending)
    return pending


async def admin_client_cookies(session: AsyncSession):
    """Return (admin_user, access_token_cookies) tuple."""
    admin = await make_user(session, username="siteadmin", role=MemberRoleEnum.ADMIN)
    await add_registered_user(admin.username, MemberRoleEnum.ADMIN)
    return admin, auth_cookies(make_access_token(admin))


# ── GET /admin/users ──────────────────────────────────────────────────────────


class TestGetVerifiedUsers:
    async def test_admin_gets_user_list(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await admin_client_cookies(session)
        await make_user(session, username="alice")
        await make_user(session, username="bob")

        r = await client.get("/admin/users", cookies=cookies)
        assert r.status_code == 200
        usernames = [u["username"] for u in r.json()]
        assert "alice" in usernames
        assert "bob" in usernames

    async def test_non_admin_is_blocked(self, client: AsyncClient, session: AsyncSession):
        user = await make_user(session, role=MemberRoleEnum.USER)
        await add_registered_user(user.username, MemberRoleEnum.USER)
        token = make_access_token(user)

        r = await client.get("/admin/users", cookies=auth_cookies(token))
        assert r.status_code == 403

    async def test_unauthenticated_is_blocked(self, client: AsyncClient):
        r = await client.get("/admin/users")
        assert r.status_code == 403


# ── GET /admin/users/pending ──────────────────────────────────────────────────


class TestGetPendingUsers:
    async def test_returns_pending_users(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await admin_client_cookies(session)
        await make_pending_user(session, username="pendingpete")

        r = await client.get("/admin/users/pending", cookies=cookies)
        assert r.status_code == 200
        usernames = [u["username"] for u in r.json()]
        assert "pendingpete" in usernames

    async def test_returns_empty_list_when_no_pending(
        self, client: AsyncClient, session: AsyncSession
    ):
        _, cookies = await admin_client_cookies(session)
        r = await client.get("/admin/users/pending", cookies=cookies)
        assert r.status_code == 200
        assert r.json() == []


# ── GET /admin/users/stats ────────────────────────────────────────────────────


class TestGetUserStats:
    async def test_stats_reflect_created_users(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await admin_client_cookies(session)
        await make_user(session, role=MemberRoleEnum.USER)
        await make_user(session, role=MemberRoleEnum.VIP)
        await make_pending_user(session)

        r = await client.get("/admin/users/stats", cookies=cookies)
        assert r.status_code == 200
        body = r.json()

        # At least what we inserted; other tests may have added more
        assert body["user"] >= 1
        assert body["vip"] >= 1
        assert body["pending"] >= 1

    async def test_stats_has_expected_keys(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await admin_client_cookies(session)
        r = await client.get("/admin/users/stats", cookies=cookies)
        body = r.json()
        assert all(k in body for k in ("user", "vip", "admin", "pending"))


# ── PATCH /admin/users/{username}/role ────────────────────────────────────────


class TestUpdateUserRole:
    async def test_promotes_user_to_vip(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await admin_client_cookies(session)
        target = await make_user(session, username="promoteme", role=MemberRoleEnum.USER)

        r = await client.patch(
            f"/admin/users/{target.username}/role",
            json={"role": "vip"},
            cookies=cookies,
        )
        assert r.status_code == 200

        await session.refresh(target)
        assert target.role == MemberRoleEnum.VIP

    async def test_demotes_vip_to_user(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await admin_client_cookies(session)
        target = await make_user(session, username="demoteme", role=MemberRoleEnum.VIP)

        r = await client.patch(
            f"/admin/users/{target.username}/role",
            json={"role": "user"},
            cookies=cookies,
        )
        assert r.status_code == 200

        await session.refresh(target)
        assert target.role == MemberRoleEnum.USER

    async def test_role_change_updates_redis_immediately(
        self, client: AsyncClient, session: AsyncSession
    ):
        """
        After the PATCH, Redis must reflect the new role so that
        RoleChecker enforces it on the very next request.
        """
        _, cookies = await admin_client_cookies(session)
        target = await make_user(session, username="redispromote", role=MemberRoleEnum.USER)
        await add_registered_user(target.username, MemberRoleEnum.USER)

        await client.patch(
            f"/admin/users/{target.username}/role",
            json={"role": "admin"},
            cookies=cookies,
        )

        live_role = await get_user(target.username)
        assert live_role == MemberRoleEnum.ADMIN

    async def test_unknown_user_returns_404(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await admin_client_cookies(session)
        r = await client.patch(
            "/admin/users/doesnotexist/role",
            json={"role": "user"},
            cookies=cookies,
        )
        assert r.status_code == 404

    async def test_invalid_role_value_returns_422(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await admin_client_cookies(session)
        target = await make_user(session, username="badrole")
        r = await client.patch(
            f"/admin/users/{target.username}/role",
            json={"role": "superuser"},
            cookies=cookies,
        )
        assert r.status_code == 422


# ── POST /admin/users/{username}/approve ──────────────────────────────────────


class TestApprovePendingUser:
    async def test_approve_moves_to_verified(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await admin_client_cookies(session)
        pending = await make_pending_user(session, username="approveme")

        r = await client.post(f"/admin/users/{pending.username}/approve", cookies=cookies)
        assert r.status_code == 200
        body = r.json()
        assert body["username"] == "approveme"

    async def test_approve_removes_from_pending(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await admin_client_cookies(session)
        pending = await make_pending_user(session, username="removepending")

        await client.post(f"/admin/users/{pending.username}/approve", cookies=cookies)

        # Pending list should no longer contain this user
        r = await client.get("/admin/users/pending", cookies=cookies)
        usernames = [u["username"] for u in r.json()]
        assert "removepending" not in usernames

    async def test_approve_already_verified_returns_409(
        self, client: AsyncClient, session: AsyncSession
    ):
        _, cookies = await admin_client_cookies(session)
        verified = await make_user(session, username="alreadyverified")

        r = await client.post(f"/admin/users/{verified.username}/approve", cookies=cookies)
        assert r.status_code == 409

    async def test_approve_unknown_user_returns_404(
        self, client: AsyncClient, session: AsyncSession
    ):
        _, cookies = await admin_client_cookies(session)
        r = await client.post("/admin/users/nobody/approve", cookies=cookies)
        assert r.status_code == 404


# ── POST /admin/users/{username}/reject ───────────────────────────────────────


class TestRejectPendingUser:
    async def test_reject_creates_rejected_record(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await admin_client_cookies(session)
        pending = await make_pending_user(session, username="rejectme")

        r = await client.post(f"/admin/users/{pending.username}/reject", cookies=cookies)
        assert r.status_code == 200
        body = r.json()
        assert body["username"] == "rejectme"
        assert "rejected_date" in body

    async def test_reject_removes_from_pending(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await admin_client_cookies(session)
        pending = await make_pending_user(session, username="rejectclean")

        await client.post(f"/admin/users/{pending.username}/reject", cookies=cookies)

        r = await client.get("/admin/users/pending", cookies=cookies)
        usernames = [u["username"] for u in r.json()]
        assert "rejectclean" not in usernames

    async def test_reject_already_verified_returns_409(
        self, client: AsyncClient, session: AsyncSession
    ):
        _, cookies = await admin_client_cookies(session)
        verified = await make_user(session, username="cannotreject")

        r = await client.post(f"/admin/users/{verified.username}/reject", cookies=cookies)
        assert r.status_code == 409

    async def test_reject_unknown_user_returns_404(
        self, client: AsyncClient, session: AsyncSession
    ):
        _, cookies = await admin_client_cookies(session)
        r = await client.post("/admin/users/nobody/reject", cookies=cookies)
        assert r.status_code == 404
