from sqlmodel import SQLModel, Field, Column
from datetime import date, datetime, time, timedelta
from uuid import UUID, uuid4
from sqlalchemy import Enum as SAEnum, UniqueConstraint
from sqlalchemy import Interval, Time as Time
import sqlalchemy.dialects.postgresql as postgres
from src.db.db_models import *
from typing import Optional
from pydantic import BaseModel


"""##################################
    NOTE: START REGISTRATION DATA 
##################################"""


# TODO:
# NOTE:
class UserID(SQLModel, table=True):
    """
    The ID of any account, whether currently pending or approved. Primary identifier
    """

    __tablename__ = "user_id"

    id: UUID = Field(
        sa_column=Column(postgres.UUID, primary_key=True, default=uuid4, nullable=False)
    )

    def __str__(self):
        return f"<User: {self.id}"


class PendingUser(UserBaseModel, table=True):
    """
    The user registers with their own information, and db automatically assigns an id.
    Upon valid parameters, data sent to server will first generate a user_id then insert into pending_user table.
    """

    __tablename__ = "pending_user"

    user_id: UUID = Field(foreign_key="user_id.id", primary_key=True, nullable=False)

    username: str = Field(
        sa_column=Column(
            postgres.VARCHAR,
            unique=True,
            index=True,
            nullable=False,
        ),
        min_length=2,
        max_length=32,
    )
    email: Optional[str] = Field(
        sa_column=Column(
            postgres.VARCHAR,
            unique=True,
            index=True,
            nullable=True,
        ),
        max_length=64,
    )
    password_hash: str = Field(
        sa_column=Column(postgres.VARCHAR, nullable=False), exclude=True
    )

    nickname: Optional[str] = Field(min_length=2, index=False, nullable=True)
    join_date: date = Field(
        sa_column=Column(postgres.DATE, default=date.today, index=False, nullable=False)
    )
    request: Optional[str] = Field(nullable=True)

    def __str__(self):
        return f"<User: `{self.username}` identified by id: `{self.user_id}` and name `{self.nickname}`>"


class User(UserBaseModel, table=True):
    """
    Verified user, deletes entry in corresponding pending_user table
    """

    __tablename__ = "user"

    user_id: UUID = Field(
        foreign_key="user_id.id", primary_key=True, nullable=False
    )

    username: str = Field(
        sa_column=Column(
            postgres.VARCHAR,
            unique=True,
            index=True,
            nullable=False,
        ),
        min_length=2,
        max_length=32,
    )
    email: Optional[str] = Field(
        sa_column=Column(
            postgres.VARCHAR,
            unique=True,
            index=True,
            nullable=True,
        ),
        max_length=64,
    )
    password_hash: str = Field(
        sa_column=Column(postgres.VARCHAR, nullable=False), exclude=True
    )

    nickname: Optional[str] = Field(index=False, nullable=True)
    join_date: date = Field(
        sa_column=Column(postgres.DATE, index=False, nullable=False)
    )
    request: Optional[str] = Field(nullable=True)
    verified_date: date = Field(
        sa_column=Column(postgres.DATE, default=date.today, index=False, nullable=False)
    )
    last_login_date: date = Field(
        sa_column=Column(postgres.DATE, default=date.today, index=False, nullable=True)
    )
    role: MemberRoleEnum = Field(
        default=MemberRoleEnum.USER,
        sa_column=Column(
            SAEnum(MemberRoleEnum, name="member_role_enum", create_type=False, values_callable=lambda x: [e.value for e in x]),
            index=True,
            nullable=False,
        ),
    )

    def __str__(self):
        return f"<User: `{self.user_id}` is `{self.nickname}` and has the role `{self.role}`"


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
