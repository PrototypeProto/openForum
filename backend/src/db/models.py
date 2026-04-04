from sqlmodel import SQLModel, Field, Column
from datetime import date, datetime, time, timedelta
from uuid import UUID, uuid4
from sqlalchemy import Enum as SAEnum, UniqueConstraint, func
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
# NOTE: Under no circumstances, should a user's UUID
# be easily accessible by anyone that is not the user themselves
class UserID(SQLModel, table=True):
    """
    The ID of any account, whether currently pending or approved. Primary identifier
    """

    __tablename__ = "user_id"

    id: Optional[UUID] = Field(
        sa_column=Column(
            postgres.UUID,
            primary_key=True,
            server_default=func.gen_random_uuid(),
            nullable=False,
        ),
        default=None,
    )

    def __str__(self):
        return f"<User: {self.id}"


class PendingUser(SQLModel, table=True):
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
    join_date: Optional[date] = Field(
        sa_column=Column(
            postgres.DATE,
            server_default=func.current_date(),
            index=False,
            nullable=False,
        ),
        default=None,
    )
    request: Optional[str] = Field(nullable=True)

    def __str__(self):
        return f"<User: `{self.username}` identified by id: `{self.user_id}` and name `{self.nickname}`>"


class User(SQLModel, table=True):
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
    verified_date: Optional[date] = Field(
        sa_column=Column(
            postgres.DATE,
            server_default=func.current_date(),
            index=False,
            nullable=False,
        ),
        default=None,
    )
    last_login_date: Optional[date] = Field(
        sa_column=Column(
            postgres.DATE,
            server_default=func.current_date(),
            index=False,
            nullable=True,
        ),
        default=None,
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
            server_default=MemberRoleEnum.USER.value,
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


class Topic(SQLModel, table=True):
    """
    Top-level category that groups related threads.
    Organized under broader categories, in order
        e.g. 'General Discussion', 'Announcements', 'Random'

    thread & reply count and last_activity_at & last_thread_id have corresponding triggers to keep them updated.
    group_id is optional to allow creation of a topic before assigning it to a grouping.
    """

    __tablename__ = "topic"

    topic_id: Optional[UUID] = Field(
        sa_column=Column(
            postgres.UUID,
            primary_key=True,
            server_default=func.gen_random_uuid(),
            nullable=False,
        ),
        default=None,
    )
    group_id: Optional[UUID] = Field(foreign_key="topic_group.group_id", nullable=True)
    name: str = Field(
        sa_column=Column(postgres.VARCHAR, unique=True, nullable=False),
        max_length=100,
    )
    description: Optional[str] = Field(sa_column=Column(postgres.TEXT, nullable=True))
    icon_url: Optional[str] = Field(sa_column=Column(postgres.VARCHAR, nullable=True))
    # lower number = higher up in the list
    display_order: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, server_default="0"),
        default=0,
    )
    thread_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, server_default="0"),
        default=0,
    )
    reply_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, server_default="0"),
        default=0,
    )
    created_at: Optional[datetime] = Field(
        sa_column=Column(
            postgres.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
        ),
        default=None,
    )
    is_locked: bool = Field(
        sa_column=Column(postgres.BOOLEAN, nullable=False, server_default="false"),
        default=False,
    )  # if True, no new threads can be created
    last_activity_at: Optional[datetime] = Field(
        sa_column=Column(postgres.TIMESTAMP(timezone=True), nullable=True)
    )
    last_thread_id: Optional[UUID] = Field(nullable=True, default=None)


class TopicGroup(SQLModel, table=True):
    """
    Organizes the topic table under broader categories.
    """

    __tablename__ = "topic_group"

    group_id: Optional[UUID] = Field(
        sa_column=Column(
            postgres.UUID,
            primary_key=True,
            server_default=func.gen_random_uuid(),
            nullable=False,
        ),
        default=None,
    )
    name: str = Field(
        sa_column=Column(postgres.VARCHAR, unique=True, nullable=False),
        max_length=100,
    )
    display_order: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, server_default="0"),
        default=0,
    )


class Thread(SQLModel, table=True):
    """
    A thread/post inside a topic, created by a user.

    reply_count and vote counts have corresponding triggers to keep them updated.

    NOTE: view_count is currently not planned to be supported.
    TODO: Requires triggers: updated_at, reply_count, vote_counts, [view_count tentative]
    NOTE: Must do a JOIN to add user.username — author_id will NOT be shared publicly.
    """

    __tablename__ = "thread"

    thread_id: Optional[UUID] = Field(
        sa_column=Column(
            postgres.UUID,
            primary_key=True,
            server_default=func.gen_random_uuid(),
            nullable=False,
        ),
        default=None,
    )
    topic_id: UUID = Field(foreign_key="topic.topic_id", nullable=False)
    author_id: UUID = Field(foreign_key="user_id.id", nullable=False, exclude=True)
    title: str = Field(
        sa_column=Column(postgres.VARCHAR, nullable=False),
        max_length=200,
    )
    body: str = Field(sa_column=Column(postgres.TEXT, nullable=False))
    created_at: Optional[datetime] = Field(
        sa_column=Column(
            postgres.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
        ),
        default=None,
    )
    updated_at: Optional[datetime] = Field(
        sa_column=Column(postgres.TIMESTAMP(timezone=True), nullable=True)
    )
    is_pinned: bool = Field(
        sa_column=Column(postgres.BOOLEAN, nullable=False, server_default="false"),
        default=False,
    )
    pin_expires_at: Optional[datetime] = Field(
        sa_column=Column(postgres.TIMESTAMP(timezone=True), nullable=True)
    )  # None = pinned forever
    is_locked: bool = Field(
        sa_column=Column(postgres.BOOLEAN, nullable=False, server_default="false"),
        default=False,
    )  # if True, no new replies allowed
    is_deleted: bool = Field(
        sa_column=Column(postgres.BOOLEAN, nullable=False, server_default="false"),
        default=False,
    )  # soft delete
    reply_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, server_default="0"),
        default=0,
    )
    upvote_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, server_default="0"),
        default=0,
    )
    downvote_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, server_default="0"),
        default=0,
    )
    view_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, server_default="0"),
        default=0,
    )
    last_activity_at: Optional[datetime] = Field(
        sa_column=Column(postgres.TIMESTAMP(timezone=True), nullable=True, index=True)
    )
    last_activity: Optional[UUID] = Field(nullable=True, default=None) # a replyid


class ThreadVote(SQLModel, table=True):
    """
    Tracks which user voted on which thread and whether it was up/downvoted.
    Composite PK prevents a user voting twice on the same thread.

    NOTE: dropped created_at
    TODO: trigger updating thread table
    NOTE: if user revokes their vote (unlikes their like, but not a dislike), delete entry, else update
    """

    __tablename__ = "thread_vote"

    user_id: UUID = Field(foreign_key="user_id.id", primary_key=True, nullable=False)
    thread_id: UUID = Field(
        foreign_key="thread.thread_id", primary_key=True, nullable=False
    )
    is_upvote: bool = Field(sa_column=Column(postgres.BOOLEAN, nullable=False))


# class ThreadReaction(SQLModel, table=True):
#     """
#     Emoji reactions on a thread. Max 5 unique emoji types enforced at app level.
#     Composite PK prevents a user reacting with the same emoji twice.
#     """
#     __tablename__ = "thread_reaction"
#
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
#         sa_column=Column(postgres.TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
#     )


class Reply(SQLModel, table=True):
    """
    A reply to a thread, or to another reply (nested).
    parent_reply_id = None means it's a direct thread reply.
    parent_reply_id = some UUID means it's a reply to a reply.

    TODO: trigger updating thread & topic table
    NOTE: updated_at also used as a flag to note if user has edited their post
    NOTE: affected by voting triggers
    NOTE: Must do a JOIN to add user.username — author_id will NOT be shared publicly
    """

    __tablename__ = "reply"

    reply_id: Optional[UUID] = Field(
        sa_column=Column(
            postgres.UUID,
            primary_key=True,
            server_default=func.gen_random_uuid(),
            nullable=False,
        ),
        default=None,
    )
    thread_id: UUID = Field(foreign_key="thread.thread_id", nullable=False)
    author_id: UUID = Field(foreign_key="user_id.id", nullable=False, exclude=True)
    parent_reply_id: Optional[UUID] = Field(
        foreign_key="reply.reply_id", nullable=True, default=None
    )  # self-referential — None means top-level reply
    body: str = Field(sa_column=Column(postgres.TEXT, nullable=False))
    created_at: Optional[datetime] = Field(
        sa_column=Column(
            postgres.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
        ),
        default=None,
    )
    updated_at: Optional[datetime] = Field(
        sa_column=Column(postgres.TIMESTAMP(timezone=True), nullable=True)
    )
    is_deleted: bool = Field(
        sa_column=Column(postgres.BOOLEAN, nullable=False, server_default="false"),
        default=False,
    )  # soft delete — keeps thread structure intact
    upvote_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, server_default="0"),
        default=0,
    )
    downvote_count: int = Field(
        sa_column=Column(postgres.INTEGER, nullable=False, server_default="0"),
        default=0,
    )


class ReplyVote(SQLModel, table=True):
    """
    Tracks which user voted on which reply and whether it was up or down.
    Composite PK prevents a user voting twice on the same reply.

    TODO: trigger affects reply vote count
    NOTE: see thread_vote for similar behavior
    """

    __tablename__ = "reply_vote"

    user_id: UUID = Field(foreign_key="user_id.id", primary_key=True, nullable=False)
    reply_id: UUID = Field(
        foreign_key="reply.reply_id", primary_key=True, nullable=False
    )
    is_upvote: bool = Field(sa_column=Column(postgres.BOOLEAN, nullable=False))


# class ReplyAttachment(SQLModel, table=True):
#     """
#     An attachment on a reply — either an image URL or a hyperlink.
#     A reply can have multiple attachments.
#
#     TODO: WIP on how to best implement
#     """
#
#     __tablename__ = "reply_attachment"
#
#     attachment_id: UUID = Field(
#         sa_column=Column(postgres.UUID, primary_key=True, server_default=func.gen_random_uuid(), nullable=False)
#     )
#     reply_id: UUID = Field(foreign_key="reply.reply_id", nullable=False)
#     attachment_type: AttachmentType = Field(
#         sa_column=Column(
#             SAEnum(
#                 AttachmentType,
#                 name="attachment_type",
#                 create_type=False,
#                 values_callable=lambda x: [e.value for e in x],
#             ),
#             nullable=False,
#         )
#     )
#     url: str = Field(
#         sa_column=Column(postgres.VARCHAR, nullable=False), max_length=2048
#     )
#     label: Optional[str] = Field(
#         sa_column=Column(postgres.VARCHAR, nullable=True), max_length=200
#     )  # display text for hyperlinks
#     created_at: datetime = Field(
#         sa_column=Column(
#             postgres.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
#         )
#     )


"""##################################
    NOTE: END FORUM DATA 
##################################"""
