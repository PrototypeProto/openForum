from src.db.models import (
    User,
    UserID,
    PendingUser,
)
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, desc, update, insert, delete
from datetime import date, datetime, timedelta
from uuid import UUID
from typing import List
from src.db.db_models import MemberRoleEnum, VerifyUserModel
from src.db.models import PendingUser
from src.db.roles_redis import set_user_role, get_user_role
from src.db.users_redis import add_registered_user, get_user, remove_user
from src.auth.service import AuthService
REFRESH_TOKEN_EXPIRY_MIN = 15

auth_service = AuthService()

class AdminService:
    """
    Handles business logic (db access) for the {/auth} route
    enforce proper data insertions
    """

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Helper Methods
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


    async def get_all_users(self, session: AsyncSession) -> List[User]:
        query = select(User)
        res = await session.exec(query)
        return res.all()

    async def get_pending_users(self, session: AsyncSession) -> List[PendingUser]:
        query = select(PendingUser.user_id, PendingUser.username)
        res = await session.exec(query)
        return res.all()



    async def verify_admin(self, token_details: dict) -> bool:
        # check if current user is admin
        if token_details is None or token_details.get('user') is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid permission to access requested resources")
        
        # Check if user is authorized to exec admin priv
        if not await self.is_user_admin(token_details.get('user').get('user_id'), session):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid permission to access requested resources")

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Existence Validation - Log in / Sign up
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    async def raise_user_privilege(self, username: str, role: MemberRoleEnum, session: AsyncSession) -> User:
        user: User = await auth_service.get_username_from_user_table(username, session)
        user.role = role.value
        await session.commit()
        await session.refresh(user)
        return user
    
    async def is_verified_user(self, username: str, session: AsyncSession):
        '''
        Checks redis for a User w/ `username`, else repopulates caches and returns answer from DB
        '''
        exists = await get_user(username)
        if exists:
            return True

        user = await auth_service.get_username_from_user_table(username, session)
        if user is None:
            return False
        
        await add_registered_user(username)
        return True

    async def get_all_users(self, session: AsyncSession):
        statement = select(User).order_by(desc(User.join_date))
        result = await session.exec(statement)
        return result.all()

    async def is_user_admin(self, username: str, session: AsyncSession) -> bool:
        '''
        Query redis first then db
        '''
        if username is None:
            return False

        role = get_user_role(username)
        if role == MemberRoleEnum.ADMIN.value:
            return True

        if role is None: # redis cache is empty, must fill it and query pgsql
            query = select(User.role).where(User.username == username)
            res = await session.exec(query)
            set_user_role(username, res.first()[0]) # update redis value
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
        pending_user: PendingUser = await auth_service.get_username_from_user_pending_table(
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

    