from src.db.models import (
    User,
    UserID,
    PendingUser,
)
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, desc, update, insert, delete, exists
from datetime import date, datetime, timedelta
from .utils import generate_passwd_hash, verify_passwd
from uuid import UUID
from typing import List
from .utils import create_access_token, decode_token, verify_passwd
from .schemas import AccessTokenUserData, LoginResultEnum
from src.db.db_models import MemberRoleEnum, VerifyUserModel
from src.db.models import PendingUser
from src.db.users_redis import add_registered_user, get_user
from .dependencies import get_current_user_by_username, get_current_user_uuid

REFRESH_TOKEN_EXPIRY_MIN = 60 * 24  # 1 day
user_service

class AuthService:
    """
    Handles business logic (db access) for the {/auth} route
    """

    # # # # # # # # # # # # # # # # # # # #
    #   Feature methods
    # # # # # # # # # # # # # # # # # # # #
    async def register_user(
        self, data: RegisterUserModel, session: AsyncSession
    ) -> User:
        # TODO: Parse for SQL Injection

        # Create user_id then a pending_user entry
        user_id = UserID()
        session.add(user_id)
        await session.commit()
        await session.refresh(user_id)

        pending_user = PendingUser(
            **data.model_dump(exclude={"password"}),
            password_hash=generate_passwd_hash(data.password),
            join_date=date.today(),
            user_id=user_id.id,
        )

        session.add(pending_user)
        await session.commit()
        await session.refresh(pending_user)
        return pending_user

    def generate_tokens(self, data_dict: dict) -> tuple:
        access_token = create_access_token(
            user_data=data_dict,
        )

        refresh_token = create_access_token(
            user_data=data_dict,
            refresh=True,
            expiry=timedelta(minutes=REFRESH_TOKEN_EXPIRY_MIN),
        )

        return access_token, refresh_token

    # # # # # # # # # # # # # # # # # # # #
    #   Auth validation methods
    # # # # # # # # # # # # # # # # # # # #
    async def is_valid_user_token(
        self, token_details: dict, session: AsyncSession
    ) -> bool:
        """
        Checks redis for a User w/ `username`, else repopulates caches and returns answer from DB
        Useful as a user exists method
        """
        if (
            token_details is None
            or token_details.get("user") is None
            or token_details.get("user").get("username") is None
        ):
            return False

        username = token_details.get("user").get("username")
        exists = await get_user(username)
        if exists:
            return True

        user = await self.get_username_from_user_table(username, session)
        if user is None:
            return False

        await add_registered_user(username)
        return True

    # # # # # # # # # # # # # # # # # # # #
    #   Safety checking methods
    # # # # # # # # # # # # # # # # # # # #
    async def username_exists(
        self, username: str, session: AsyncSession
    ) -> LoginResultEnum:
        if await self.get_username_from_user_table(username, session) is not None:
            return LoginResultEnum.VALID
        elif await self.get_username_from_user_pending_table(username, session):
            return LoginResultEnum.PENDING
        return LoginResultEnum.DNE

    async def email_exists(self, email: str, session: AsyncSession) -> LoginResultEnum:
        if await self.get_email_from_user_table(email, session) is not None:
            return LoginResultEnum.VALID
        elif await self.get_email_from_user_pending_table(email, session) is not None:
            return LoginResultEnum.PENDING
        return LoginResultEnum.DNE

    async def uuid_exists(self, uuid: UUID, session: AsyncSession, search_user_else_unverified=True) -> bool:
        stmt = select(exists().where(User.user_id == uuid))
        res = await session.exec(stmt)
        return False if res.one_or_none() is None else res.one()

    # # # # # # # # # # # # # # # # # # # #
    #   Helper methods
    # # # # # # # # # # # # # # # # # # # #
    async def get_username_from_user_table(
        self, username: str, session: AsyncSession
    ) -> User:
        statement = select(User).where(User.username == username)
        result = await session.exec(statement)
        return result.first()

    async def get_username_from_user_pending_table(
        self, username: str, session: AsyncSession
    ) -> PendingUser:
        statement = select(PendingUser).where(PendingUser.username == username)
        result = await session.exec(statement)
        return result.first()

    async def get_email_from_user_table(
        self, email: str, session: AsyncSession
    ) -> User:
        statement = select(User).where(User.email == email)
        result = await session.exec(statement)
        return result.first()

    async def get_email_from_user_pending_table(
        self, email: str, session: AsyncSession
    ) -> PendingUser:
        statement = select(PendingUser).where(PendingUser.email == email)
        result = await session.exec(statement)
        return result.first()
