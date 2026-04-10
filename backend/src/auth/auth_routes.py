from typing import Annotated
from src.config import Config
from fastapi import APIRouter, Depends, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession
from .service import AuthService
from src.db.main import get_session
from .utils import verify_passwd, seconds_until_expiry
from datetime import datetime, timezone
from .dependencies import (
    RefreshTokenBearer,
    access_token_bearer,
    require_user,
)
from src.db.redis_client import (
    add_jti_to_blocklist,
    store_refresh_token,
    get_refresh_token_owner,
    delete_refresh_token,
    revoke_all_user_refresh_tokens,
    get_user,
    add_registered_user,
)
from src.db.schemas import UserRegister, UserLogin, UserData
from .schemas import AccessTokenUserData, LoginResultEnum
from src.exceptions import (
    AlreadyExistsError,
    InvalidCredentialsError,
    NotFoundError,
    TokenExpiredError,
    SessionRevokedError,
    RefreshTokenReuseError,
    UnauthorizedError,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
auth_service = AuthService()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.post("/signup", response_model=UserData, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserRegister,
    session: SessionDependency,
) -> UserData:
    if not user_data.email:
        user_data.email = None
    if not user_data.nickname:
        user_data.nickname = None
    if not user_data.request:
        user_data.request = None

    if (
        await auth_service.username_exists(user_data.username, session)
        != LoginResultEnum.DNE
    ):
        raise AlreadyExistsError("User with that username already exists")

    if user_data.email is not None:
        if (
            await auth_service.email_exists(user_data.email, session)
            != LoginResultEnum.DNE
        ):
            raise AlreadyExistsError("User with that email already exists")

    return await auth_service.register_user(user_data, session)


@router.post("/login", status_code=status.HTTP_200_OK)
async def login_user(
    login_data: UserLogin,
    session: SessionDependency,
    response: Response,
):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    user = await auth_service.get_user_with_username(login_data.username, session)
    if user is None or not verify_passwd(login_data.password, user.password_hash):
        raise InvalidCredentialsError()

    if not await get_user(user.username):
        await add_registered_user(user.username, user.role)

    access_token, refresh_token = await auth_service.generate_tokens(user)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=Config.cookie_secure,
        samesite="lax",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=Config.cookie_secure,
        samesite="lax",
    )

    return {
        "message": "login successful",
        "user": {
            "user_id": str(user.user_id),
            "username": user.username,
            "nickname": user.nickname,
            "role": user.role,
        },
    }


@router.post("/refresh_token")
async def rotate_refresh_token(
    response: Response,
    token_details: dict = Depends(RefreshTokenBearer()),
    session: SessionDependency = None,
):
    if datetime.fromtimestamp(token_details["exp"], tz=timezone.utc) <= datetime.now(
        timezone.utc
    ):
        raise TokenExpiredError("Refresh token has expired")

    jti = token_details["jti"]
    username = token_details["user"]["username"]

    owner = await get_refresh_token_owner(jti)

    if owner is None:
        await revoke_all_user_refresh_tokens(username)
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        raise RefreshTokenReuseError(
            "Refresh token reuse detected. All sessions revoked. Please log in again."
        )

    if owner != username:
        await delete_refresh_token(jti)
        raise UnauthorizedError("Invalid refresh token")

    await delete_refresh_token(jti)
    ttl = seconds_until_expiry(token_details)
    await add_jti_to_blocklist(jti, max(ttl, 1))

    user = await auth_service.get_user_with_username(username, session)
    if user is None:
        raise UnauthorizedError("User no longer exists")

    access_token, new_refresh_token = await auth_service.generate_tokens(user)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=Config.cookie_secure,
        samesite="lax",
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=Config.cookie_secure,
        samesite="lax",
    )

    return {"message": "tokens rotated"}


@router.get("/me")
async def get_current_user(
    session: SessionDependency,
    token_details: dict = require_user,
):
    username = token_details["user"]["username"]
    user = await auth_service.get_user_with_username(username, session)
    if user is None:
        raise NotFoundError("User not found")
    return user


@router.post("/logout")
async def revoke_token(
    response: Response,
    token_details: dict = access_token_bearer,
):
    jti = token_details["jti"]
    username = token_details["user"]["username"]

    ttl = seconds_until_expiry(token_details)
    await add_jti_to_blocklist(jti, max(ttl, 1))
    await revoke_all_user_refresh_tokens(username)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return {"message": "Logged out successfully"}
