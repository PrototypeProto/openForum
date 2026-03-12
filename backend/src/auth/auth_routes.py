from typing import Optional, Union, Annotated, List

"""
    Optional[type(s)]
    Union() or (type | None)
    Annotated[type, "annotation textr"]
"""
from fastapi import FastAPI, Header, APIRouter, Depends
from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from .service import AuthService
from src.db.main import get_session
from .utils import create_access_token, decode_token, verify_passwd
from datetime import datetime, timedelta
from .dependencies import (
    RefreshTokenBearer,
    access_token_bearer,
    get_current_user_by_username,
)
from src.db.redis import add_jti_to_blocklist
from src.db.db_models import UserDataModel, RegisterUserModel, LoginUserModel, MemberRoleEnum
from .schemas import AccessTokenUserData, LoginResultEnum
from uuid import UUID
from src.db.models import User

"""
    A custom route to access users
    simple CRUD routes
    calls service() methods to perform business logic
"""
REFRESH_TOKEN_EXPIRY_DAYS = 2

auth_router = APIRouter()
auth_service = AuthService()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@auth_router.post(
    "/signup", response_model=UserDataModel, status_code=status.HTTP_201_CREATED
)
async def create_user(
    user_data: RegisterUserModel, session: SessionDependency
) -> UserDataModel:
    if await auth_service.username_exists(user_data.username, session) != LoginResultEnum.DNE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User with username already exists",
        )

    if await auth_service.email_exists(user_data.email, session) != LoginResultEnum.DNE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User with email already exists",
        )

    new_user = await auth_service.register_user(user_data, session)
    return new_user


@auth_router.post("/login", status_code=status.HTTP_200_OK)
async def login_user(login_data: LoginUserModel, session: SessionDependency):
    user = await auth_service.get_username_from_user_table(login_data.username, session)
    if user is None:
        user1 = await auth_service.get_username_from_user_pending_table(login_data.username, session)
        if user1 is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is currently pending approval, try again later...")

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid username and/or password",
        )

    data_dict = AccessTokenUserData(
        user_id=str(user.user_id),
        username=user.username,
        role=user.role,
        nickname=user.nickname,
    ).model_dump()

    if verify_passwd(login_data.password, user.password_hash):
        access_token, refresh_token = auth_service.generate_tokens(data_dict)
        if access_token is not None and refresh_token is not None:
            return JSONResponse(
                content={
                    "message": "login successful",
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user": data_dict,
                }
            )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Invalid username and/or password"
    )


@auth_router.get(
    "/all_users",
    response_model=List[UserDataModel],
)
async def get_all_users(session: SessionDependency):
    users = await auth_service.get_all_users(session)
    return users


@auth_router.get("/refresh_token")
async def get_new_access_token(token_details: dict = Depends(RefreshTokenBearer())):
    expiry_timestamp = token_details["exp"]

    if datetime.fromtimestamp(expiry_timestamp) > datetime.now():
        new_access_token = create_access_token(user_data=token_details["user"])

        return JSONResponse(content={"access_token": new_access_token})

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid/Expired token"
    )


@auth_router.get("/me")
async def get_current_user(user=Depends(get_current_user_by_username)):
    return user


@auth_router.get("/logout")
async def revoke_token(token_details: dict = access_token_bearer):
    if token_details is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid token was provided.",
        )

    jti = token_details["jti"]

    await add_jti_to_blocklist(jti)

    return JSONResponse(
        content={"message": "Logged out successfully"}, status_code=status.HTTP_200_OK
    )

@auth_router.patch("/{username}/promotion/vip")
async def promote_to_vip(username: str, session: SessionDependency, token_details: dict = access_token_bearer):
    # check if current user is admin
    if token_details is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid permission to access requested resources")
    
    admin_id = token_details.get('user').get('user_id')
    if admin_id is None or not auth_service.is_user_admin(admin_id, session):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid permission to access requested resources")

    # check if user_id is valid
    user = await auth_service.get_username_from_user_table(username, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user does not exist")
        
    # promote user else error
    res = await auth_service.raise_user_privilege(user, session)
    if res is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Failed to update perms")
    if res.role != MemberRoleEnum.VIP.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Failed to update perms")
    
@auth_router.post("/admin")
async def make_admin(session: SessionDependency, token_details: dict = access_token_bearer):
    if token_details is None or token_details.get('user') is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid perms1")

    user = await auth_service.get_username_from_user_table(token_details.get('user').get('username'), session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid perms2")

    res = await auth_service.make_admin(user.username, session)
    print(res)
    return res

@auth_router.post("/{username}/promotion/user", response_model=User)
async def authorize_pending_user(username: str, session: SessionDependency):
    new_user = await auth_service.promote_pending_to_user(username, session)
    if new_user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Failed to update perms")
    print(new_user)
    return new_user

    