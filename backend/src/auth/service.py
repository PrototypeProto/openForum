from src.db.models import (
    User,
    UserID,
    PendingUser,
)
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, desc, update, insert, delete
from datetime import date, datetime, timedelta
from .utils import generate_passwd_hash, verify_passwd
from uuid import UUID
from typing import List
from .utils import create_access_token, decode_token, verify_passwd
from .schemas import AccessTokenUserData, LoginResultEnum
from src.db.db_models import MemberRoleEnum, VerifyUserModel
from src.db.models import PendingUser
from src.db.users_redis import add_registered_user, get_user

REFRESH_TOKEN_EXPIRY_MIN = 60 * 24 # 1 day


class AuthService:
    """
    Handles business logic (db access) for the {/auth} route
    enforce proper data insertions
    """

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Helper Methods
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
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

    async def username_exists(
        self, username: str, session: AsyncSession
    ) -> LoginResultEnum:
        if await self.get_username_from_user_table(username, session) is not None:
            return LoginResultEnum.VALID
        elif await self.get_username_from_user_pending_table(username, session):
            return LoginResultEnum.PENDING
        return LoginResultEnum.DNE

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

    async def email_exists(self, email: str, session: AsyncSession) -> LoginResultEnum:
        if await self.get_email_from_user_table(email, session) is not None:
            return LoginResultEnum.VALID
        elif await self.get_email_from_user_pending_table(email, session) is not None:
            return LoginResultEnum.PENDING
        return LoginResultEnum.DNE

    async def get_all_users(self, session: AsyncSession) -> List[User]:
        query = select(User)
        res = await session.exec(query)
        return res.all()

    async def get_unverified_users(self, session: AsyncSession) -> List[PendingUser]:
        query = select(PendingUser)
        res = await session.exec(query)
        return res.all()

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Existence Validation - Log in / Sign up
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
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

    async def raise_user_privilege(self, user: User, session: AsyncSession) -> User:
        user.role = MemberRoleEnum.VIP.value
        await session.commit()
        await session.refresh(user)
        return user

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Creation
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    async def create_user(
        self, user_data: User_CreateModel, session: AsyncSession
    ) -> User:
        user_data_dict = user_data.model_dump()
        new_user = User(**user_data_dict)

        new_user.role = MemberRoleEnum.UNREGISTERED
        new_user.passwd_hash = generate_passwd_hash(user_data.passwd)
        new_user.join_date = date.today()
        new_user.is_verified = False

        session.add(new_user)
        await session.commit()
        return new_user

    # TODO: implement the login logic in the user_routes.py
    # NOTE: Can combine the password hash logic here as well?
    async def valid_user_login(
        self, user_login_details: User_LoginModel, session: AsyncSession
    ) -> bool:
        # if not self.username_exists(user_login_details.username, session):
        #     return False

        statement = select(User.passwd_hash).where(
            User.username == user_login_details.username
        )
        result = await session.exec(statement)
        hashed_password = result.first()

        # Unnecessary?
        if hashed_password is None:
            return false

        return verify_passwd(user_login_details.passwd, hashed_password)

    async def get_all_users(self, session: AsyncSession):
        statement = select(User).order_by(desc(User.join_date))

        result = await session.exec(statement)
        return result.all()

    async def is_user_admin(self, user_id: UUID, session: AsyncSession) -> bool:
        query = select(User.role).where(User.user_id == user_id)
        res = await session.exec(query)
        return res.first()[0] == MemberRoleEnum.ADMIN.value

    async def make_admin(self, username: UUID, session: AsyncSession) -> dict:
        query = (
            update(User)
            .where(User.username == username)
            .values({"role": MemberRoleEnum.ADMIN.value})
        )
        res = await session.exec(query)
        await session.commit()
        return res.last_updated_params()

    async def promote_pending_to_user(self, username: str, session: AsyncSession):
        pending_user: PendingUser = await self.get_username_from_user_pending_table(
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
        res = await session.exec(stmt)

        if res.rowcount == 0:
            raise Exception("Failed to delete user")

        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async def is_verified_user(self, token_details: dict, session: AsyncSession) -> bool:
        '''
        Checks redis for a User w/ `username`, else repopulates caches and returns answer from DB
        Useful as a user exists method
        '''
        if token_details is None or token_details.get('user') is None or token_details.get('user').get('username') is None:
            return False
        
        username = token_details.get('user').get('username')
        exists = await get_user(username)
        if exists:
            return True

        user = await self.get_username_from_user_table(username, session)
        if user is None:
            return False
        
        await add_registered_user(username)
        return True

    # TODO: Create update user password method
    # async def update_user(self, user_uid:str, update_data:UserUpdateModel, session:AsyncSession):
    #     user_to_update = await self.get_user_by_email(user_uid, session)

    #     if user_to_update is not None:
    #         update_data_dict = update_data.model_dump()
    #         update_data_dict["time_modified"] = datetime.now()

    #         for k, v in update_data_dict.items():
    #             setattr(user_to_update, k, v)

    #         await session.commit()

    #         return user_to_update
    #     else:
    #         return None

    # async def delete_user(self, user_uid:str, session:AsyncSession) -> bool:
    #     user_to_delete = await self.get_user_by_email(user_uid, session)

    #     if user_to_delete is not None:
    #         await session.delete(user_to_delete)

    #         await session.commit()

    #         return True

    #     else:
    #         return False
