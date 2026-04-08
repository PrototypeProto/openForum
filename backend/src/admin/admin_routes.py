from typing import Optional, Union, Annotated, List, Tuple
from fastapi import FastAPI, Header, APIRouter, Depends, Query, Body
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
    UserTypeEnum,
)
from uuid import UUID
from src.db.models import User, PendingUser
from src.db.read_models import *


router = APIRouter(prefix="/admin", tags=["admin"])
admin_service = AdminService()
auth_service = AuthService()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/users", response_model=List[UserRead])
async def get_verified_users(
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    """
    GET /admin/users
    Lists all verified users for the admin panel.
    NOTE: exclude self when modifying user values to avoid conflicts like accidentally demoting self
    """
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions"
        )
    return await admin_service.get_users(session)


@router.get("/users/pending", response_model=List[PendingUserRead])
async def get_pending_users(
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    """
    GET /admin/users/pending
    Lists all pending users for the admin approval panel.
    """
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions"
        )
    return await admin_service.get_pending_users(session)


@router.get("/users/stats", response_model=UserStats)
async def get_users(
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions"
        )
    return await admin_service.get_user_stats(session)


@router.patch("/users/{username}/role")
async def update_user_role(
    username: str,
    session: SessionDependency,
    token_details: dict = access_token_bearer,
    role: MemberRoleEnum = Body(..., embed=True),
):
    """
    Updates a verified user's site role
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
    res = await admin_service.update_user_role(username, role, session)
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Failed to update perms"
        )


@router.post("/users/{username}/approve", response_model=UserRead)
async def approve_pending_user(
    username: str, session: SessionDependency, token_details: dict = access_token_bearer
):
    """
    Admin grants access to the website to a pending user
    NOTE: Copies pending_user entry to user table and then deletes the pending_user entry
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
        new_user = await admin_service.approve_pending_user(username, session)
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


@router.post("/users/{username}/reject", response_model=RejectedUserRead)
async def reject_pending_user(
    username: str, session: SessionDependency, token_details: dict = access_token_bearer
):
    """
    Admin rejects access to the website to a pending user
    NOTE: Copies pending_user entry to rejected user and deletes pending_user
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

    if not approve:
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
