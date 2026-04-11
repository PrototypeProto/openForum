"""
tests/test_admin_service.py
───────────────────────────
Service-layer unit tests for AdminService.

Calls the singleton directly — no HTTP. Tests the Redis-first resolution paths,
DB fallbacks, cache backfill, and the user approval/rejection state machine.

Covers:
  is_user_admin       — Redis hit (admin), Redis hit (non-admin), DB fallback,
                        DB backfill, unknown user
  is_verified_user    — Redis hit, DB fallback + backfill, unknown user
  get_user_stats      — correct grouping across roles + pending count
  update_user_role    — DB mutation + immediate Redis overwrite
  approve_pending_user — PendingUser → User migration
  reject_pending_user  — PendingUser → RejectedUser migration
"""

from datetime import date

from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import generate_passwd_hash
from src.db.enums import MemberRoleEnum
from src.db.models import PendingUser, UserID
from src.db.redis_client import add_registered_user, get_user
from tests.conftest import make_user
from tests.constants import TEST_PASSWORD_STUB, TEST_PENDING_REQUEST

# ── Helpers ────────────────────────────────────────────────────────────────────


async def make_pending(
    session: AsyncSession, *, username: str, password: str = TEST_PASSWORD_STUB
) -> PendingUser:
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


# ── is_user_admin ──────────────────────────────────────────────────────────────


class TestIsUserAdmin:
    async def test_redis_hit_admin_returns_true(self, admin_svc, session: AsyncSession):
        user = await make_user(session, username="redisadmin", role=MemberRoleEnum.ADMIN)
        await add_registered_user(user.username, MemberRoleEnum.ADMIN)

        assert await admin_svc.is_user_admin("redisadmin", session) is True

    async def test_redis_hit_non_admin_returns_false(self, admin_svc, session: AsyncSession):
        user = await make_user(session, username="redisuser", role=MemberRoleEnum.USER)
        await add_registered_user(user.username, MemberRoleEnum.USER)

        assert await admin_svc.is_user_admin("redisuser", session) is False

    async def test_db_fallback_admin_returns_true(self, admin_svc, session: AsyncSession):
        """Redis miss → DB hit for admin."""
        await make_user(session, username="dbadmin", role=MemberRoleEnum.ADMIN)
        # Deliberately skip Redis prime

        assert await admin_svc.is_user_admin("dbadmin", session) is True

    async def test_db_fallback_backfills_redis(self, admin_svc, session: AsyncSession):
        await make_user(session, username="backfilladmin", role=MemberRoleEnum.ADMIN)

        await admin_svc.is_user_admin("backfilladmin", session)

        cached = await get_user("backfilladmin")
        assert cached == MemberRoleEnum.ADMIN

    async def test_unknown_user_returns_false(self, admin_svc, session: AsyncSession):
        assert await admin_svc.is_user_admin("ghost", session) is False

    async def test_empty_username_returns_false(self, admin_svc, session: AsyncSession):
        assert await admin_svc.is_user_admin("", session) is False


# ── is_verified_user ───────────────────────────────────────────────────────────


class TestIsVerifiedUser:
    async def test_redis_hit_returns_true(self, admin_svc, session: AsyncSession):
        user = await make_user(session, username="cachedverified")
        await add_registered_user(user.username, MemberRoleEnum.USER)

        assert await admin_svc.is_verified_user("cachedverified", session) is True

    async def test_db_fallback_returns_true(self, admin_svc, session: AsyncSession):
        await make_user(session, username="dbverified")

        assert await admin_svc.is_verified_user("dbverified", session) is True

    async def test_db_fallback_backfills_redis(self, admin_svc, session: AsyncSession):
        user = await make_user(session, username="backfillverified", role=MemberRoleEnum.VIP)

        await admin_svc.is_verified_user("backfillverified", session)

        cached = await get_user("backfillverified")
        assert cached == MemberRoleEnum.VIP

    async def test_pending_user_returns_false(self, admin_svc, session: AsyncSession):
        """Pending users are not verified — they should not appear as verified."""
        await make_pending(session, username="stillpending")

        assert await admin_svc.is_verified_user("stillpending", session) is False

    async def test_unknown_user_returns_false(self, admin_svc, session: AsyncSession):
        assert await admin_svc.is_verified_user("nobody", session) is False

    async def test_empty_username_returns_false(self, admin_svc, session: AsyncSession):
        assert await admin_svc.is_verified_user("", session) is False


# ── get_user_stats ─────────────────────────────────────────────────────────────


class TestGetUserStats:
    async def test_counts_match_inserted_users(self, admin_svc, session: AsyncSession):
        await make_user(session, role=MemberRoleEnum.USER)
        await make_user(session, role=MemberRoleEnum.USER)
        await make_user(session, role=MemberRoleEnum.VIP)
        await make_user(session, role=MemberRoleEnum.ADMIN)
        await make_pending(session, username="statspen1")
        await make_pending(session, username="statspen2")

        stats = await admin_svc.get_user_stats(session)

        assert stats.user >= 2
        assert stats.vip >= 1
        assert stats.admin >= 1
        assert stats.pending >= 2

    async def test_stats_has_all_fields(self, admin_svc, session: AsyncSession):
        stats = await admin_svc.get_user_stats(session)
        assert hasattr(stats, "user")
        assert hasattr(stats, "vip")
        assert hasattr(stats, "admin")
        assert hasattr(stats, "pending")

    async def test_stats_are_non_negative(self, admin_svc, session: AsyncSession):
        stats = await admin_svc.get_user_stats(session)
        assert stats.user >= 0
        assert stats.vip >= 0
        assert stats.admin >= 0
        assert stats.pending >= 0


# ── update_user_role ───────────────────────────────────────────────────────────


class TestUpdateUserRole:
    async def test_updates_role_in_db(self, admin_svc, session: AsyncSession):
        user = await make_user(session, username="promotable", role=MemberRoleEnum.USER)

        await admin_svc.update_user_role("promotable", MemberRoleEnum.VIP, session)

        await session.refresh(user)
        assert user.role == MemberRoleEnum.VIP

    async def test_overwrites_redis_immediately(self, admin_svc, session: AsyncSession):
        """Redis must reflect the new role before the next request hits RoleChecker."""
        user = await make_user(session, username="redisoverwrite", role=MemberRoleEnum.USER)
        await add_registered_user(user.username, MemberRoleEnum.USER)

        await admin_svc.update_user_role("redisoverwrite", MemberRoleEnum.ADMIN, session)

        cached = await get_user("redisoverwrite")
        assert cached == MemberRoleEnum.ADMIN

    async def test_demote_from_admin_to_user(self, admin_svc, session: AsyncSession):
        user = await make_user(session, username="demotable", role=MemberRoleEnum.ADMIN)

        await admin_svc.update_user_role("demotable", MemberRoleEnum.USER, session)

        await session.refresh(user)
        assert user.role == MemberRoleEnum.USER


# ── approve_pending_user ───────────────────────────────────────────────────────


class TestApprovePendingUser:
    async def test_creates_verified_user_row(self, admin_svc, session: AsyncSession):
        await make_pending(session, username="approvesvc")

        result = await admin_svc.approve_pending_user("approvesvc", session)

        assert result is not None
        assert result.username == "approvesvc"
        assert result.role == MemberRoleEnum.USER

    async def test_removes_from_pending(self, admin_svc, session: AsyncSession):
        """After approval the pending row must be gone."""
        from src.auth.service import auth_service

        await make_pending(session, username="clearpending")
        await admin_svc.approve_pending_user("clearpending", session)

        still_pending = await auth_service.get_pending_user_with_username("clearpending", session)
        assert still_pending is None

    async def test_unknown_pending_user_returns_none(self, admin_svc, session: AsyncSession):
        result = await admin_svc.approve_pending_user("doesnotexist", session)
        assert result is None

    async def test_verified_date_set_to_today(self, admin_svc, session: AsyncSession):
        await make_pending(session, username="verifydate")
        result = await admin_svc.approve_pending_user("verifydate", session)
        assert result.verified_date == date.today()


# ── reject_pending_user ────────────────────────────────────────────────────────


class TestRejectPendingUser:
    async def test_creates_rejected_record(self, admin_svc, session: AsyncSession):
        await make_pending(session, username="rejectsvc")

        result = await admin_svc.reject_pending_user("rejectsvc", session)

        assert result is not None
        assert result.username == "rejectsvc"
        assert result.rejected_date == date.today()

    async def test_removes_from_pending(self, admin_svc, session: AsyncSession):
        from src.auth.service import auth_service

        await make_pending(session, username="rejectclean")
        await admin_svc.reject_pending_user("rejectclean", session)

        still_pending = await auth_service.get_pending_user_with_username("rejectclean", session)
        assert still_pending is None

    async def test_unknown_pending_user_returns_none(self, admin_svc, session: AsyncSession):
        result = await admin_svc.reject_pending_user("nobody", session)
        assert result is None
