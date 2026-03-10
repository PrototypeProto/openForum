from sqlmodel import SQLModel, Field, Column
from datetime import date, datetime, time, timedelta
from uuid import UUID
from typing import Optional
from enum import Enum
from pydantic import BaseModel


"""##################################
    NOTE: START REGISTRATION DATA 
##################################"""
"""
Enum
"""


class MemberRoleEnum(str, Enum):
    ADMIN = "admin"
    VIP = "vip"
    USER = "user"


"""
    What we use to enforce data input
"""


class UserBaseModel(SQLModel):
    username: str = Field(min_length=2, max_length=32)
    email: Optional[str] = Field(default=None, max_length=64)
    nickname: Optional[str] = Field(default=None)


class RegisterUserModel(UserBaseModel):
    password: str = Field(nullable=False)
    request: Optional[str]


class UserDataModel(UserBaseModel):
    user_id: UUID


class LoginUserModel(SQLModel):
    username: str = Field(max_length=32, nullable=False)
    password: str = Field(nullable=False)




"""##################################
    NOTE: END REGISTRATION DATA 
##################################"""


"""##################################
    NOTE: START TEMP DATA 
##################################"""

"""##################################
    NOTE: END TEMP DATA 
##################################"""


"""##################################
    NOTE: START TEMP DATA 
##################################"""

"""##################################
    NOTE: END TEMP DATA 
##################################"""


"""##################################
    NOTE: START TEMP DATA 
##################################"""

"""##################################
    NOTE: END REGISTRATION DATA 
##################################"""
