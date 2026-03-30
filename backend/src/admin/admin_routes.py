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



admin_router = APIRouter()
admin_service = AdminService()
auth_service = AuthService()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@admin_router.get(
    "/all_users",
    response_model=List[UserDataModel],
)
async def get_all_users(session: SessionDependency, token_details: dict = access_token_bearer):
    '''
    NOTE: Subject for overhaul to just return user count
    Subject for removal unless wanting to list all users for some reason
    '''
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions")   
    users = await admin_service.get_all_users(session)
    return users

@admin_router.get("/unapproved/users", response_model=List[Tuple[UUID, str]])
async def get_unapproved_users(session: SessionDependency, token_details: dict = access_token_bearer):
    '''
    Gets a list of newly registered users who want access to the site [(userid, username),]
    '''
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions")
    return await admin_service.get_pending_users(session)

@admin_router.patch("/{username}/promotion/{role}")
async def promote_user(
    username: str, role: MemberRoleEnum, session: SessionDependency, token_details: dict = access_token_bearer
):
    '''
    Admin elevates a verified user's permission level
    '''
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions") 

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
    
    print(f'promoted user: {res}')

@admin_router.post("/{username}/promotion/user", response_model=User)
async def authorize_pending_user(username: str, session: SessionDependency, token_details: dict = access_token_bearer):
    '''
    Admin grants access to the website to a newly registered user
    '''
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions")  

    if await admin_service.is_verified_user(username, session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Failed to update perms. User is already verified"
        )
    
    new_user = None
    try:
        new_user = await admin_service.promote_pending_to_user(username, session)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to delete unverified user", 
        ) 
    if new_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Failed to update perms"
        )
    return new_user
