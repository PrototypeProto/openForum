from sqlmodel import SQLModel, Field, Column
from datetime import date, datetime, time, timedelta
from uuid import UUID, uuid4
from sqlalchemy import Enum as SAEnum, UniqueConstraint
from sqlalchemy import Interval, Time as Time
from sqlalchemy.dialects import postgresql as postgres
from src.db.db_models import *
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, date
from enum import Enum

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
    The user registers with their own information, and db automatically assigns an id from UserID table.
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
    Verified user, deletes entry in corresponding pending_user table once a pending user is verified
    """

    __tablename__ = "user"

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
            SAEnum(
                MemberRoleEnum,
                name="member_role_enum",
                create_type=False,
                values_callable=lambda x: [e.value for e in x],
            ),
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
    NOTE: START FORUM DATA 
##################################"""

# # # # # # # # # # # # # # # # # # # #
# Topic
# # # # # # # # # # # # # # # # # # # #


class Topic(SQLModel, table=True):
    """
    Top-level category that groups related threads.
    e.g. 'General Discussion', 'Announcements', 'Random'
    """

    __tablename__ = "topic"

    topic_id: UUID = Field(
        sa_column=Column(postgres.UUID, primary_key=True, default=uuid4, nullable=False)
    )
    name: str = Field(
        sa_column=Column(postgres.VARCHAR, unique=True, nullable=False),
        max_length=100,
    )
    description: Optional[str] = Field(sa_column=Column(postgres.TEXT, nullable=True))
    icon_url: Optional[str] = Field(sa_column=Column(postgres.VARCHAR, nullable=True))
    # lower number = higher up in the list
    display_order: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, default=0), default=0
    )
    thread_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, default=0), default=0
    )
    reply_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, default=0), default=0
    )
    created_at: datetime = Field(
        sa_column=Column(
            postgres.TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow
        )
    )
    is_locked: bool = Field(
        sa_column=Column(postgres.BOOLEAN, nullable=False, default=False), default=False
    )  # if True, no new threads can be created


# # # # # # # # # # # # # # # # # # # #
# Thread
# # # # # # # # # # # # # # # # # # # #


class Thread(SQLModel, table=True):
    """
    A thread/post inside a topic, created by a user.
    """

    __tablename__ = "thread"

    thread_id: UUID = Field(
        sa_column=Column(postgres.UUID, primary_key=True, default=uuid4, nullable=False)
    )
    topic_id: UUID = Field(foreign_key="topic.topic_id", nullable=False)
    author_id: UUID = Field(foreign_key="user_id.id", nullable=False)
    title: str = Field(
        sa_column=Column(postgres.VARCHAR, nullable=False),
        max_length=200,
    )
    body: str = Field(sa_column=Column(postgres.TEXT, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(
            postgres.TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow
        )
    )
    updated_at: Optional[datetime] = Field(
        sa_column=Column(postgres.TIMESTAMP(timezone=True), nullable=True)
    )
    is_pinned: bool = Field(
        sa_column=Column(postgres.BOOLEAN, nullable=False, default=False), default=False
    )
    pin_expires_at: Optional[datetime] = Field(
        sa_column=Column(postgres.TIMESTAMP(timezone=True), nullable=True)
    )  # None = pinned forever
    is_locked: bool = Field(
        sa_column=Column(postgres.BOOLEAN, nullable=False, default=False), default=False
    )  # if True, no new replies allowed
    is_deleted: bool = Field(
        sa_column=Column(postgres.BOOLEAN, nullable=False, default=False), default=False
    )  # soft delete
    reply_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, default=0), default=0
    )
    upvote_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, default=0), default=0
    )
    downvote_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, default=0), default=0
    )
    view_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, default=0), default=0
    )


# # # # # # # # # # # # # # # # # # # #
# Thread Vote (upvote/downvote)
# # # # # # # # # # # # # # # # # # # #


class ThreadVote(SQLModel, table=True):
    """
    Tracks which user voted on which thread and whether it was up or down.
    Composite PK prevents a user voting twice on the same thread.
    """

    __tablename__ = "thread_vote"

    user_id: UUID = Field(foreign_key="user_id.id", primary_key=True, nullable=False)
    thread_id: UUID = Field(
        foreign_key="thread.thread_id", primary_key=True, nullable=False
    )
    is_upvote: bool = Field(sa_column=Column(postgres.BOOLEAN, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(
            postgres.TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow
        )
    )


# # # # # # # # # # # # # # # # # # # #
# Thread Reaction
# # # # # # # # # # # # # # # # # # # #

# class ThreadReaction(SQLModel, table=True):
#     """
#     Emoji reactions on a thread. Max 5 unique emoji types enforced at app level.
#     Composite PK prevents a user reacting with the same emoji twice.
#     """
#     __tablename__ = "thread_reaction"

#     user_id: UUID = Field(foreign_key="user_id.id", primary_key=True, nullable=False)
#     thread_id: UUID = Field(foreign_key="thread.thread_id", primary_key=True, nullable=False)
#     emoji: ReactionEmoji = Field(
#         sa_column=Column(
#             SAEnum(ReactionEmoji, name="reaction_emoji", create_type=False,
#                    values_callable=lambda x: [e.value for e in x]),
#             primary_key=True,
#             nullable=False,
#         )
#     )
#     created_at: datetime = Field(
#         sa_column=Column(postgres.TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
#     )


# # # # # # # # # # # # # # # # # # # #
# Reply
# # # # # # # # # # # # # # # # # # # #


class Reply(SQLModel, table=True):
    """
    A reply to a thread, or to another reply (nested).
    parent_reply_id = None means it's a direct thread reply.
    parent_reply_id = some UUID means it's a reply to a reply.
    """

    __tablename__ = "reply"

    reply_id: UUID = Field(
        sa_column=Column(postgres.UUID, primary_key=True, default=uuid4, nullable=False)
    )
    thread_id: UUID = Field(foreign_key="thread.thread_id", nullable=False)
    author_id: UUID = Field(foreign_key="user_id.id", nullable=False)
    parent_reply_id: Optional[UUID] = Field(
        foreign_key="reply.reply_id", nullable=True, default=None
    )  # self-referential — None means top-level reply
    body: str = Field(sa_column=Column(postgres.TEXT, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(
            postgres.TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow
        )
    )
    updated_at: Optional[datetime] = Field(
        sa_column=Column(postgres.TIMESTAMP(timezone=True), nullable=True)
    )
    is_deleted: bool = Field(
        sa_column=Column(postgres.BOOLEAN, nullable=False, default=False), default=False
    )  # soft delete — keeps thread structure intact
    upvote_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, default=0), default=0
    )
    downvote_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, default=0), default=0
    )


# # # # # # # # # # # # # # # # # # # #
# Reply Vote
# # # # # # # # # # # # # # # # # # # #


class ReplyVote(SQLModel, table=True):
    """
    Tracks which user voted on which reply and whether it was up or down.
    Composite PK prevents a user voting twice on the same reply.
    """

    __tablename__ = "reply_vote"

    user_id: UUID = Field(foreign_key="user_id.id", primary_key=True, nullable=False)
    reply_id: UUID = Field(
        foreign_key="reply.reply_id", primary_key=True, nullable=False
    )
    is_upvote: bool = Field(sa_column=Column(postgres.BOOLEAN, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(
            postgres.TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow
        )
    )


# # # # # # # # # # # # # # # # # # # #
# Reply Attachment
# # # # # # # # # # # # # # # # # # # #


class ReplyAttachment(SQLModel, table=True):
    """
    An attachment on a reply — either an image URL or a hyperlink.
    A reply can have multiple attachments.
    """

    __tablename__ = "reply_attachment"

    attachment_id: UUID = Field(
        sa_column=Column(postgres.UUID, primary_key=True, default=uuid4, nullable=False)
    )
    reply_id: UUID = Field(foreign_key="reply.reply_id", nullable=False)
    attachment_type: AttachmentType = Field(
        sa_column=Column(
            SAEnum(
                AttachmentType,
                name="attachment_type",
                create_type=False,
                values_callable=lambda x: [e.value for e in x],
            ),
            nullable=False,
        )
    )
    url: str = Field(
        sa_column=Column(postgres.VARCHAR, nullable=False), max_length=2048
    )
    label: Optional[str] = Field(
        sa_column=Column(postgres.VARCHAR, nullable=True), max_length=200
    )  # display text for hyperlinks
    created_at: datetime = Field(
        sa_column=Column(
            postgres.TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow
        )
    )


"""##################################
    NOTE: END FORUM DATA 
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
