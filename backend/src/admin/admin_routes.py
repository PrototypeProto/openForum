from typing import Optional, Union, Annotated, List, Tuple
from fastapi import FastAPI, Header, APIRouter, Depends
from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from .service import AdminService
from src.auth.service import AuthService
from src.db.main import get_session
from datetime import datetime, timedelta
from src.auth.dependencies import (
    RefreshTokenBearer,
    access_token_bearer,
)
from src.db.roles_redis import set_user_role, get_user_role
from src.db.db_models import (
    UserDataModel,
    RegisterUserModel,
    LoginUserModel,
    MemberRoleEnum,
)
from uuid import UUID
from src.db.models import User, PendingUser
from src.db.read_models import *


router = APIRouter(prefix="/admin", tags=["admin"])
admin_service = AdminService()
auth_service = AuthService()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/all_users",
    response_model=List[UserDataModel],
)
async def get_all_users(
    session: SessionDependency, token_details: dict = access_token_bearer
):
    """
    NOTE: Subject for overhaul to just return user count
    Subject for removal unless wanting to list all users for some reason
    """
    # print(token_details)
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions"
        )
    users = await admin_service.get_all_users(session)
    return users


@router.get("/unapproved/users", response_model=List[PendingUserRead])
async def get_unapproved_users(session: SessionDependency, token_details: dict = access_token_bearer):
    """
    GET /admin/unapproved/users
    Returns full detail of all pending users for the admin approval panel.
    """
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions")
    return await admin_service.get_pending_users(session)


@router.patch("/{username}/promotion/{role}")
async def promote_user(
    username: str,
    role: MemberRoleEnum,
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    """
    Admin elevates a verified user's permission level
    """
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions"
        )

    # check if user_id is valid
    if not await admin_service.is_verified_user(username, session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="user does not exist"
        )

    # promote user else error
    res = await admin_service.update_user_privilege(username, role, session)
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Failed to update perms"
        )

    print(f"promoted user: {res}")


@router.post("/{username}/promotion/user", response_model=User)
async def authorize_pending_user(
    username: str, session: SessionDependency, token_details: dict = access_token_bearer
):
    """
    Admin grants access to the website to a newly registered user
    """
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions"
        )

    if await admin_service.is_verified_user(username, session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Failed to update perms. User is already verified",
        )

    new_user = None
    try:
        new_user = await admin_service.promote_pending_to_user(username, session)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete unverified user",
        )
    if new_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Failed to update perms"
        )
    return new_user


@router.post(
    "/{username}/rejection",
    response_model=RejectedUserRead,
    status_code=status.HTTP_201_CREATED,
)
async def reject_pending_user(
    username: str, session: SessionDependency, token_details: dict = access_token_bearer
):
    """
    POST /admin/{username}/rejection
    Admin rejects a pending user, moving them from pending_user to rejected_user.
    The pending_user row is deleted; the rejected_user row is kept for audit.
    """
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions"
        )

    if await admin_service.is_verified_user(username, session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is already verified — cannot reject",
        )

    try:
        rejected = await admin_service.reject_pending_user(username, session)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to reject user"
        )

    if rejected is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pending user not found"
        )

    return rejected
