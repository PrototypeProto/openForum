from datetime import date

from sqlmodel import delete, desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.service import AuthService
from src.db.enums import MemberRoleEnum
from src.db.models import (
    PendingUser,
    RejectedUser,
    User,
)
from src.db.redis_client import add_registered_user, get_user
from src.db.schemas import *

auth_service = AuthService()


class AdminService:
    """
    Handles business logic for the {/admin} route
    Only ADMINS may use this
    """

    # # # # # # # # # # # # # # # # # # # # # # # #
    #   Core Methods
    # # # # # # # # # # # # # # # # # # # # # # # #
    async def get_pending_users(self, session: AsyncSession) -> list[PendingUserRead]:
        """Returns full detail of all pending users for the admin approval view."""
        result = await session.exec(select(PendingUser).order_by(PendingUser.join_date.asc()))
        rows = result.all()
        return [
            PendingUserRead(
                user_id=r.user_id,
                username=r.username,
                email=r.email,
                nickname=r.nickname,
                join_date=r.join_date,
                request=r.request,
            )
            for r in rows
        ]

    async def update_user_role(
        self, username: str, role: MemberRoleEnum, session: AsyncSession
    ) -> User:
        user: User = await auth_service.get_user_with_username(username, session)
        user.role = role.value
        await session.commit()
        await session.refresh(user)
        # Overwrite Redis immediately so RoleChecker sees the new role on the
        # very next request. The stale-token cross-check will then revoke the
        # user's current token and force a re-login.
        await add_registered_user(user.username, user.role)
        return user

    async def get_users(self, session: AsyncSession) -> list[UserRead]:
        query = select(User).order_by(desc(User.join_date))
        result = await session.exec(query)
        return [
            UserRead(
                user_id=r.user_id,
                username=r.username,
                nickname=r.nickname,
                join_date=r.join_date,
                role=r.role,
            )
            for r in result.all()
        ]

    async def approve_pending_user(self, username: str, session: AsyncSession) -> User:
        pending_user: PendingUser = await auth_service.get_pending_user_with_username(
            username, session
        )
        if pending_user is None:
            return None

        user: User = User(
            **pending_user.model_dump(),
            password_hash=pending_user.password_hash,
            verified_date=date.today(),
            last_login_date=None,
            role=MemberRoleEnum.USER.value,
        )

        stmt = delete(PendingUser).where(PendingUser.user_id == pending_user.user_id)
        await session.exec(stmt)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async def reject_pending_user(self, username: str, session: AsyncSession) -> RejectedUserRead:
        """
        Copies the pending_user row to rejected_user, then deletes the pending_user entry.
        Returns the created RejectedUser record.
        """
        pending_user: PendingUser = await auth_service.get_pending_user_with_username(
            username, session
        )
        if pending_user is None:
            return None

        rejected = RejectedUser(
            user_id=pending_user.user_id,
            username=pending_user.username,
            email=pending_user.email,
            password_hash=pending_user.password_hash,
            nickname=pending_user.nickname,
            join_date=pending_user.join_date,
            request=pending_user.request,
            rejected_date=date.today(),
        )

        await session.delete(pending_user)
        session.add(rejected)
        await session.commit()
        await session.refresh(rejected)

        return RejectedUserRead(
            user_id=rejected.user_id,
            username=rejected.username,
            email=rejected.email,
            nickname=rejected.nickname,
            join_date=rejected.join_date,
            request=rejected.request,
            rejected_date=rejected.rejected_date,
        )

    async def get_user_stats(self, session: AsyncSession) -> UserStats:
        # Count verified users grouped by role in one query
        role_counts = (
            await session.exec(
                select(User.role, func.count(User.user_id).label("cnt")).group_by(User.role)
            )
        ).all()

        # Count pending users
        pending_count = (await session.exec(select(func.count(PendingUser.user_id)))).one()

        stats = UserStats(pending=pending_count)
        for role, count in role_counts:
            if role == MemberRoleEnum.USER:
                stats.user = count
            elif role == MemberRoleEnum.VIP:
                stats.vip = count
            elif role == MemberRoleEnum.ADMIN:
                stats.admin = count

        return stats

    # # # # # # # # # # # # # # # # # # # # # # # #
    # Validation Methods
    # # # # # # # # # # # # # # # # # # # # # # # #
    async def is_verified_user(self, username: str, session: AsyncSession) -> bool:
        """
        Checks redis for a User w/ `username`, else repopulates caches and returns answer from DB
        Useful as a user exists method
        """
        if not username:
            return False

        exists = await get_user(username)
        if exists:
            return True

        user = await auth_service.get_user_with_username(username, session)
        if user is None:
            return False

        await add_registered_user(user.username, user.role)
        return True

    async def is_user_admin(self, username: str, session: AsyncSession) -> bool:
        """Redis-first admin check. Always returns bool (never None)."""
        if not username:
            return False

        role = await get_user(username)
        if role is not None:
            return role == MemberRoleEnum.ADMIN

        # Cache miss — go to DB and backfill
        query = select(User.role).where(User.username == username)
        res = await session.exec(query)
        role = res.first()
        if role is None:
            return False
        await add_registered_user(username, role)
        return role == MemberRoleEnum.ADMIN

    # NOTE: deprecated after rolechecking implemented. Subject to deletion
    # async def verify_admin(self, token_details: dict, session: AsyncSession) -> bool:
    #     # check if current user is admin
    #     if not token_details or not token_details.get("user"):
    #         return False

    #     if not await self.is_verified_user(
    #         token_details.get("user").get("username"), session
    #     ):
    #         return False  # TODO: return Exception/Error (later when creating custom errors)

    #     # Check if user is authorized to exec admin priv
    #     return await self.is_user_admin(
    #         token_details.get("user").get("username"), session
    #     ):
    #         return False
    #         # raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid permission to access requested resources")
    #     return True
