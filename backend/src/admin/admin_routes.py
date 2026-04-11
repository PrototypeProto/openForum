from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.dependencies import require_admin
from src.auth.service import AuthService
from src.db.enums import MemberRoleEnum
from src.db.main import get_session
from src.db.schemas import *
from src.exceptions import (
    AlreadyVerifiedError,
    InternalError,
    NotFoundError,
)

from .service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])
admin_service = AdminService()
auth_service = AuthService()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/users", response_model=list[UserRead])
async def get_verified_users(
    session: SessionDependency,
    token_details: dict = require_admin,
):
    return await admin_service.get_users(session)


@router.get("/users/pending", response_model=list[PendingUserRead])
async def get_pending_users(
    session: SessionDependency,
    token_details: dict = require_admin,
):
    return await admin_service.get_pending_users(session)


@router.get("/users/stats", response_model=UserStats)
async def get_user_stats(
    session: SessionDependency,
    token_details: dict = require_admin,
):
    return await admin_service.get_user_stats(session)


@router.patch("/users/{username}/role")
async def update_user_role(
    username: str,
    session: SessionDependency,
    token_details: dict = require_admin,
    role: MemberRoleEnum = Body(..., embed=True),
):
    if not await admin_service.is_verified_user(username, session):
        raise NotFoundError("User does not exist")

    res = await admin_service.update_user_role(username, role, session)
    if res is None:
        raise InternalError("Failed to update role")


@router.post("/users/{username}/approve", response_model=UserRead)
async def approve_pending_user(
    username: str,
    session: SessionDependency,
    token_details: dict = require_admin,
):
    if await admin_service.is_verified_user(username, session):
        raise AlreadyVerifiedError("User is already verified")

    try:
        new_user = await admin_service.approve_pending_user(username, session)
    except Exception as exc:
        raise InternalError("Failed to approve user") from exc

    if new_user is None:
        raise NotFoundError("Pending user not found")

    return new_user


@router.post("/users/{username}/reject", response_model=RejectedUserRead)
async def reject_pending_user(
    username: str,
    session: SessionDependency,
    token_details: dict = require_admin,
):
    if await admin_service.is_verified_user(username, session):
        raise AlreadyVerifiedError("User is already verified")

    try:
        rejected = await admin_service.reject_pending_user(username, session)
    except Exception as exc:
        raise InternalError("Failed to reject user") from exc

    if rejected is None:
        raise NotFoundError("Pending user not found")

    return rejected
