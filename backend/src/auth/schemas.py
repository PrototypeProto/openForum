from pydantic import BaseModel
from enum import Enum


class LoginResultEnum(Enum):
    PENDING = ("pending",)
    VALID = ("valid",)
    DNE = None


class AccessTokenUserData(BaseModel):
    """
    Payload embedded in both access and refresh tokens.
    Role is intentionally excluded — it is verified live against Redis/DB
    on every request by RoleChecker and cross-checked for staleness.
    The frontend should source the role from GET /auth/me, not the token.
    """

    user_id: str
    username: str
    nickname: str | None
