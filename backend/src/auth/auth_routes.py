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
from src.db.db_models import UserDataModel, RegisterUserModel, LoginUserModel
from .schemas import AccessTokenUserData, LoginResultEnum


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
        print(user1)
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

    if verify_passwd(login_data.password, user.passwd_hash):
        tokens = auth_service.login_user(data_dict)
        if tokens is not None:
            access_token = tokens[0]
            refresh_token = tokens[1]

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
