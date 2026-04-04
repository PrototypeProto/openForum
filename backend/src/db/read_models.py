from sqlmodel import SQLModel, Field, Column
from uuid import UUID
from typing import Optional
from src.db.db_models import MemberRoleEnum
from datetime import date, datetime, time


class UserRead(SQLModel):
    user_id: UUID
    username: str
    nickname: Optional[str]
    join_date: date
    role: MemberRoleEnum


class UserPrivateRead(UserRead):
    email: Optional[str]
    last_login_date: Optional[date]


class PendingUserRead(SQLModel):
    user_id: UUID
    username: str
    email: Optional[str]
    nickname: Optional[str]
    join_date: date
    request: Optional[str]


# # # # # # # # # #
# Topics
# # # # # # # # # #
class TopicGroupRead(SQLModel):
    group_id: UUID
    name: str
    display_order: int


class TopicRead(SQLModel):
    topic_id: UUID
    group_id: Optional[UUID]

    name: str
    description: Optional[str]
    icon_url: Optional[str]

    display_order: int

    thread_count: int
    reply_count: int

    is_locked: bool

    last_activity_at: Optional[datetime]
    last_thread_id: Optional[UUID]

    last_poster_username: Optional[str]


# # # # # # # # # #
# Threads
# # # # # # # # # #
class ThreadRead(SQLModel):
    thread_id: UUID
    topic_id: UUID

    author_id: UUID
    author_username: str  # JOIN on user table

    title: str
    body: str

    created_at: datetime
    updated_at: Optional[datetime]

    is_pinned: bool
    is_locked: bool
    is_deleted: bool

    reply_count: int
    upvote_count: int
    downvote_count: int

    last_activity_at: Optional[datetime]
    last_reply_username: Optional[str] = None


class ThreadListItem(SQLModel):
    """
    Compact thread row for the topic listing page (/forum/{topic_name}).
    Includes the latest-activity username for the right-hand activity column.
    """
    thread_id: UUID
    title: str
 
    author_id: UUID
    author_username: str  # JOIN on user table
 
    created_at: datetime
 
    reply_count: int
    upvote_count: int
    downvote_count: int
 
    is_pinned: bool
 
    last_activity_at: Optional[datetime]
    last_reply_username: Optional[str]  # username of most recent replier (JOIN)


class ThreadWithVote(ThreadRead):
    user_vote: Optional[bool]  # True = upvote, False = downvote, None = no vote


# THREAD WRITE MODELS
class ThreadCreate(SQLModel):
    title: str = Field(max_length=200)
    body: str

class ThreadUpdate(SQLModel):
    title: Optional[str] = Field(default=None, max_length=200)
    body: Optional[str] = None
    # mod-only fields — enforce in the endpoint, not the model
    is_pinned: Optional[bool] = None
    pin_expires_at: Optional[datetime] = None
    is_locked: Optional[bool] = None

class PaginatedThreads(SQLModel):
    items: list[ThreadListItem]
    total: int
    page: int
    page_size: int
    pages: int



# # # # # # # # # #
# Replies
# # # # # # # # # #
class ReplyRead(SQLModel):
    """
    A single reply card — used on /thread/{thread_id}.
    reply_number is the 1-based creation order within the thread (body = #1).
    author_username resolved via JOIN.
    parent_author_username is the username being replied to (for the 'replying to' banner).
    """
    reply_id: UUID
    thread_id: UUID
 
    author_id: UUID
    author_username: str  # JOIN on user table
 
    parent_reply_id: Optional[UUID]
    parent_author_username: Optional[str]  # JOIN — who is being replied to
 
    body: str
    is_deleted: bool
 
    created_at: datetime
    updated_at: Optional[datetime]
 
    reply_number: int  # 1-based order of creation in the thread
 
    upvote_count: int
    downvote_count: int

class ReplyWithVote(ReplyRead):
    """ReplyRead + the requesting user's current vote state."""
    user_vote: Optional[bool]  # True = upvote, False = downvote, None = no vote

class PaginatedReplies(SQLModel):
    """
    Paginated reply list for /thread/{thread_id}.
    Page 1 returns up to 14 items (slot 1 is the thread body treated as reply #1).
    Page 2+ returns up to 15 items.
    """
    items: list[ReplyRead]
    total: int
    page: int
    page_size: int
    pages: int


# REPLY WRITE MODELS
class ReplyCreate(SQLModel):
    body: str
    parent_reply_id: Optional[UUID] = None


class ReplyUpdate(SQLModel):
    body: str  # only the body is ever editable by the author


# # # # # # # # # #
# VOTE PAYLOADS / RESULTS
# # # # # # # # # #
class VotePayload(SQLModel):
    is_upvote: bool


class VoteResult(SQLModel):
    """Returned after any vote action so the client can update counts in place."""
    upvote_count: int
    downvote_count: int
    user_vote: Optional[bool]  # resulting vote state after the action