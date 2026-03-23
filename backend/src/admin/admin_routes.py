from typing import Optional, Union, Annotated, List
from fastapi import FastAPI, Header, APIRouter, Depends
from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from .service import AdminService
from src.auth.service import AuthService
from src.db.main import get_session
from .utils import create_access_token, decode_token, verify_passwd
from datetime import datetime, timedelta
from src.auth.dependencies import (
    RefreshTokenBearer,
    access_token_bearer,
    get_current_user_by_username,
)
from src.db.tokens_redis import add_jti_to_blocklist
from src.db.roles_redis import set_user_role, get_user_role
from src.db.db_models import (
    UserDataModel,
    RegisterUserModel,
    LoginUserModel,
    MemberRoleEnum,
)
from .schemas import AccessTokenUserData, LoginResultEnum
from uuid import UUID
from src.db.models import User, PendingUser


REFRESH_TOKEN_EXPIRY_DAYS = 2

admin_router = APIRouter()
admin_service = AdminService()
auth_service = AuthService()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@admin_router.get(
    "/all_users",
    response_model=List[UserDataModel],
)
async def get_all_users(session: SessionDependency):
    users = await admin_service.get_all_users(session)
    return users

@admin_router.get("/unregistered/users", response_model=List[PendingUser])
async def get_unregistered_users(session: SessionDependency):
    return await admin_service.get_unverified_users(session)


@admin_router.patch("/{username}/promotion/vip")
async def promote_to_vip(
    username: str, session: SessionDependency, token_details: dict = access_token_bearer
):
    if not await admin_service.verify_admin(token_details):
        return

    # check if user_id is valid
    user = await auth_service.get_username_from_user_table(username, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="user does not exist"
        )

    # promote user else error
    res = await admin_service.raise_user_privilege(user, session)
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Failed to update perms"
        )
    if res.role != MemberRoleEnum.VIP.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Failed to update perms"
        )


@admin_router.post("/{username}/promotion/user", response_model=User)
async def authorize_pending_user(username: str, session: SessionDependency):
    new_user = await admin_service.promote_pending_to_user(username, session)
    if new_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Failed to update perms"
        )
    print(new_user)
    return new_user
