from src.db.models import (
    User,
    UserID,
    PendingUser,
)
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, desc, update, insert
from datetime import date, datetime
from .utils import generate_passwd_hash, verify_passwd
from uuid import UUID
from typing import List
from .utils import create_access_token, decode_token, verify_passwd
from .schemas import AccessTokenUserData, LoginResultEnum


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

    async def login_user(self, password: str, data_dict: dict) -> tuple:
        access_token = create_access_token(
            user_data=data_dict,
        )

        refresh_token = create_access_token(
            user_data=data_dict,
            refresh=True,
            expiry=timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
        )

        return (access_token, refresh_token)

    async def raise_current_user_privilege(
        self, user_id: UUID, model: UserPrivilegeUpdateModel, session: AsyncSession
    ):
        statement = update(User).where(User.uid == user_id).values(model)
        result = await session.exec(statement)
        await session.commit()

        return result.rowcount > 0

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
