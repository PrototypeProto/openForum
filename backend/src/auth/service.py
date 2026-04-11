from src.db.models import User, UserID, PendingUser
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, exists
from datetime import date
from uuid import UUID
from .utils import (
    generate_passwd_hash,
    verify_passwd,
    create_access_token,
    decode_token,
    REFRESH_TOKEN_EXPIRY_SECONDS,
    ACCESS_TOKEN_EXPIRY_SECONDS,
)
from .schemas import AccessTokenUserData, LoginResultEnum
from src.db.enums import MemberRoleEnum
from src.db.models import PendingUser
from src.db.schemas import RegisterUserModel
from src.db.redis_client import add_registered_user, get_user, store_refresh_token


class AuthService:
    """
    Handles business logic (db access) for the {/auth} route.
    """

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register_user(
        self, data: RegisterUserModel, session: AsyncSession
    ) -> User:
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

    # ------------------------------------------------------------------
    # Token generation
    # ------------------------------------------------------------------

    async def generate_tokens(self, user: User) -> tuple[str, str]:
        """
        Issue a fresh access + refresh token pair for `user`.
        The refresh JTI is stored in Redis so rotation and family revocation work.
        Role is NOT embedded in the token payload.
        """
        data_dict = AccessTokenUserData(
            user_id=str(user.user_id),
            username=user.username,
            nickname=user.nickname,
        ).model_dump()

        access_token = create_access_token(user_data=data_dict)
        refresh_token = create_access_token(
            user_data=data_dict,
            expiry_seconds=REFRESH_TOKEN_EXPIRY_SECONDS,
            refresh=True,
        )

        refresh_data = decode_token(refresh_token)
        if refresh_data is None:
            # Should never happen — we just created this token with a valid
            # secret and a positive expiry. If it does, something is deeply
            # wrong (secret mismatch, clock skew, etc.).
            raise RuntimeError("Failed to decode freshly issued refresh token")

        await store_refresh_token(
            jti=refresh_data["jti"],
            username=user.username,
            ttl_seconds=REFRESH_TOKEN_EXPIRY_SECONDS,
        )

        return access_token, refresh_token

    # ------------------------------------------------------------------
    # Auth validation
    # ------------------------------------------------------------------

    async def is_valid_user_token(
        self, token_details: dict, session: AsyncSession
    ) -> bool:
        """
        Checks redis for a User w/ `username`, else repopulates cache and checks DB.
        Used by the optional-auth download endpoint in tempfs.
        """
        if not token_details:
            return False
        username = (token_details.get("user") or {}).get("username")
        if not username:
            return False

        if await get_user(username):
            return True

        user = await self.get_user_with_username(username, session)
        if not user:
            return False

        await add_registered_user(user.username, user.role)
        return True

    # ------------------------------------------------------------------
    # Existence checks
    # ------------------------------------------------------------------

    async def username_exists(
        self, username: str, session: AsyncSession
    ) -> LoginResultEnum:
        if await self.get_user_with_username(username, session) is not None:
            return LoginResultEnum.VALID
        if await self.get_pending_user_with_username(username, session):
            return LoginResultEnum.PENDING
        return LoginResultEnum.DNE

    async def email_exists(self, email: str, session: AsyncSession) -> LoginResultEnum:
        if await self.get_user_with_email(email, session) is not None:
            return LoginResultEnum.VALID
        if await self.get_pending_user_with_email(email, session) is not None:
            return LoginResultEnum.PENDING
        return LoginResultEnum.DNE

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    async def get_user_with_username(
        self, username: str, session: AsyncSession
    ) -> User | None:
        return (
            await session.exec(select(User).where(User.username == username))
        ).first()

    async def get_pending_user_with_username(
        self, username: str, session: AsyncSession
    ) -> PendingUser | None:
        return (
            await session.exec(
                select(PendingUser).where(PendingUser.username == username)
            )
        ).first()

    async def get_user_with_email(
        self, email: str, session: AsyncSession
    ) -> User | None:
        return (await session.exec(select(User).where(User.email == email))).first()

    async def get_pending_user_with_email(
        self, email: str, session: AsyncSession
    ) -> PendingUser | None:
        return (
            await session.exec(select(PendingUser).where(PendingUser.email == email))
        ).first()
