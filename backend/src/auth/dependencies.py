from fastapi import Request, status, Depends
from fastapi.security import HTTPBearer
from fastapi.security.http import HTTPAuthorizationCredentials
from fastapi.exceptions import HTTPException
from .utils import decode_token
from src.db.tokens_redis import token_in_blocklist
from src.db.main import get_session
from sqlmodel.ext.asyncio.session import AsyncSession
from .service import AuthService
from typing import List, Any
from src.db.models import User

user_service = AuthService()

class TokenBearer(HTTPBearer):
    
    def __init__(self, auto_error = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        # creds = await super().__call__(request)
        token = self.get_token(request)

        # token = creds.credentials
        if not token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No token provided"
            )


        if not self.token_valid(token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token"
            )

        token_data = decode_token(token)

        if await token_in_blocklist(token_data['jti']):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail={
                    "error": "This token is invalid or has been revoked",
                    "resolution": "Please get a new token"
                }
            )

        self.verify_token_data(token_data)

        return token_data

    def get_token(self, request: Request) -> str | None:
        return request.cookies.get("access_token")  # default

    def token_valid(self, token: str) -> bool:
        token_data = decode_token(token)
        print(f"token_data: {token_data}")  # ← check this

        return token_data is not None
    
    def verify_token_data(self, token_data):
        raise NotImplementedError("Please Override this method")

class AccessTokenBearer(TokenBearer):
    def verify_token_data(self, token_data: dict) -> None:
        if token_data and token_data["refresh"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Refresh token?"
            )

class RefreshTokenBearer(TokenBearer):
    def get_token(self, request: Request) -> str | None:
        return request.cookies.get("refresh_token")

    def verify_token_data(self, token_data: dict) -> None:
        if token_data and not token_data["refresh"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please provide an refresh token"
            )


async def get_current_user_by_username(token_details: dict = Depends(AccessTokenBearer()), session: AsyncSession = Depends(get_session)) -> dict:
    user_username = token_details['user']['username']
    user = await user_service.get_user_by_username(user_username, session)
    return user

async def get_current_user_uuid(token_details: dict = Depends(AccessTokenBearer()), session: AsyncSession = Depends(get_session)) -> dict:
    user_uuid = token_details['user']['uid']
    return await user_service.get_user_by_uid(user_uuid, session)


# class RoleChecker:
#     def __init__(self, allowed_roles: List[str]) -> None:
#         self.allowed_roles = allowed_roles

#     def __call__(self, current_user: User = Depends(get_current_user_by_username)) -> Any:
#         if current_user.role in self.allowed_roles:
#             return True

#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient user permissions to access requested resource"
#         )



access_token_bearer = Depends(AccessTokenBearer())

