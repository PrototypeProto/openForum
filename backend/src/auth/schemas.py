from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from src.db.db_models import MemberRoleEnum

class LoginResultEnum(Enum):
    PENDING = ("pending",)
    VALID = ("valid",)
    DNE = None


class AccessTokenUserData(BaseModel):
    user_id: str
    username: str
    role: MemberRoleEnum
    nickname: str
