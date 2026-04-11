"""
src/db/schemas.py
─────────────────
Pydantic/SQLModel schemas for API request and response bodies.

These are NOT ORM table models (those live in src/db/models.py) and NOT
enumerations (those live in src/db/enums.py). This file contains:

  - Read schemas     — what the API returns to the client
  - Write schemas    — what the API accepts from the client
  - Internal schemas — used between service layers (e.g. FileReadModel)

Naming convention:
  <Resource>Read    — response body (outbound)
  <Resource>Create  — POST request body (inbound)
  <Resource>Update  — PATCH request body (inbound)
  <Resource>List    — compact read schema for list views
  Paginated<Resource> — paginated wrapper
"""

from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, EmailStr
from sqlmodel import Field, SQLModel

from src.db.enums import DownloadPermission, MemberRoleEnum

# ── Validation constants ──────────────────────────────────────────────────────
USERNAME_PATTERN = r"^[A-Za-z0-9_-]{2,32}$"
PASSWORD_MIN_LEN = 12
PASSWORD_MAX_LEN = 64  # bcrypt cap is 72 bytes; this is a safe ceiling
NICKNAME_MAX_LEN = 64
REQUEST_MAX_LEN = 1_000
THREAD_BODY_MAX_LEN = 10_000
REPLY_BODY_MAX_LEN = 2_000

# ── Tempfs constants ──────────────────────────────────────────────────────────
# Kept here because TempFileCreate references them as Field defaults.
# Also imported directly by tempfs/service.py.
TEMPFS_MIN_LIFETIME = 600  # 10 minutes
TEMPFS_MAX_LIFETIME = 604_800  # 1 week
TEMPFS_DEFAULT_LIFETIME = 1_800  # 30 minutes


# ── User ──────────────────────────────────────────────────────────────────────


class UserBaseModel(SQLModel):
    username: str = Field(min_length=2, max_length=32, regex=USERNAME_PATTERN)
    email: EmailStr | None = Field(default=None, max_length=254)
    nickname: str | None = Field(default=None, max_length=NICKNAME_MAX_LEN)


class RegisterUserModel(UserBaseModel):
    password: str = Field(
        min_length=PASSWORD_MIN_LEN,
        max_length=PASSWORD_MAX_LEN,
    )
    request: str | None = Field(default=None, max_length=REQUEST_MAX_LEN)


class UserRead(SQLModel):
    user_id: UUID
    username: str
    nickname: str | None
    join_date: date
    role: MemberRoleEnum


class UserPrivateRead(UserRead):
    email: str | None
    last_login_date: date | None


class PendingUserRead(SQLModel):
    user_id: UUID
    username: str
    email: str | None
    nickname: str | None
    join_date: date
    request: str | None


class RejectedUserRead(SQLModel):
    user_id: UUID
    username: str
    email: str | None
    nickname: str | None
    join_date: date
    request: str | None
    rejected_date: date


class UserStats(BaseModel):
    pending: int = 0
    user: int = 0
    vip: int = 0
    admin: int = 0


# ── Auth (request bodies) ─────────────────────────────────────────────────────


class UserBase(SQLModel):
    username: str = Field(min_length=2, max_length=32, regex=USERNAME_PATTERN)
    email: EmailStr | None = Field(default=None, max_length=254)
    nickname: str | None = Field(default=None, max_length=NICKNAME_MAX_LEN)


class UserRegister(UserBase):
    password: str = Field(
        min_length=PASSWORD_MIN_LEN,
        max_length=PASSWORD_MAX_LEN,
    )
    request: str | None = Field(default=None, max_length=REQUEST_MAX_LEN)


class UserLogin(SQLModel):
    username: str = Field(min_length=2, max_length=32, regex=USERNAME_PATTERN)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LEN)


class UserData(UserBase):
    """Response body for signup and login."""

    user_id: UUID
    role: MemberRoleEnum | None = None


# ── Topic group ───────────────────────────────────────────────────────────────


class TopicGroupRead(SQLModel):
    group_id: UUID
    name: str
    display_order: int


# ── Topic ─────────────────────────────────────────────────────────────────────


class TopicRead(SQLModel):
    topic_id: UUID
    group_id: UUID | None
    name: str
    description: str | None
    icon_url: str | None
    display_order: int
    thread_count: int
    reply_count: int
    is_locked: bool
    last_activity_at: datetime | None
    last_thread_id: UUID | None
    last_poster_username: str | None


# ── Thread ────────────────────────────────────────────────────────────────────


class ThreadRead(SQLModel):
    thread_id: UUID
    topic_id: UUID
    author_id: UUID
    author_username: str
    title: str
    body: str
    created_at: datetime
    updated_at: datetime | None
    is_pinned: bool
    is_locked: bool
    is_deleted: bool
    reply_count: int
    upvote_count: int
    downvote_count: int
    last_activity_at: datetime | None
    last_reply_username: str | None = None


class ThreadListItem(SQLModel):
    """Compact thread row for topic listing pages."""

    thread_id: UUID
    title: str
    author_id: UUID
    author_username: str
    created_at: datetime
    reply_count: int
    upvote_count: int
    downvote_count: int
    is_pinned: bool
    last_activity_at: datetime | None
    last_reply_username: str | None


class ThreadWithVote(ThreadRead):
    user_vote: bool | None  # True = upvote, False = downvote, None = no vote


class ThreadCreate(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=THREAD_BODY_MAX_LEN)


class ThreadUpdate(SQLModel):
    title: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=THREAD_BODY_MAX_LEN)
    # Mod-only fields — ownership enforced in the route handler
    is_pinned: bool | None = None
    pin_expires_at: datetime | None = None
    is_locked: bool | None = None


class PaginatedThreads(SQLModel):
    items: list[ThreadListItem]
    total: int
    page: int
    page_size: int
    pages: int


# ── Reply ─────────────────────────────────────────────────────────────────────


class ReplyRead(SQLModel):
    """
    Single reply card for thread view.
    reply_number is 1-based creation order within the thread.
    """

    reply_id: UUID
    thread_id: UUID
    author_id: UUID
    author_username: str
    parent_reply_id: UUID | None
    parent_author_username: str | None
    body: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime | None
    reply_number: int
    upvote_count: int
    downvote_count: int


class ReplyWithVote(ReplyRead):
    user_vote: bool | None = False


class PaginatedReplies(SQLModel):
    """
    Page 1 returns up to 14 items (slot 1 is the thread body as reply #1).
    Page 2+ returns up to 15 items.
    """

    items: list[ReplyWithVote]
    total: int
    page: int
    page_size: int
    pages: int


class ReplyCreate(SQLModel):
    body: str = Field(min_length=1, max_length=REPLY_BODY_MAX_LEN)
    parent_reply_id: UUID | None = None


class ReplyUpdate(SQLModel):
    body: str = Field(
        min_length=1, max_length=REPLY_BODY_MAX_LEN
    )  # only the body is editable by the author


# ── Vote ──────────────────────────────────────────────────────────────────────


class VotePayload(SQLModel):
    is_upvote: bool


class VoteResult(SQLModel):
    """Returned after any vote action so the client can update counts in-place."""

    upvote_count: int
    downvote_count: int
    user_vote: bool | None


# ── TempFS ────────────────────────────────────────────────────────────────────


class TempFileRead(SQLModel):
    file_id: UUID
    original_filename: str
    mime_type: str
    original_size: int
    stored_size: int
    is_compressed: bool
    download_permission: str
    created_at: datetime
    expires_at: datetime


class TempFileCreate(SQLModel):
    download_permission: DownloadPermission = DownloadPermission.PUBLIC
    password: str | None = None
    lifetime_seconds: int = Field(
        default=TEMPFS_DEFAULT_LIFETIME,
        ge=TEMPFS_MIN_LIFETIME,
        le=TEMPFS_MAX_LIFETIME,
    )
    compress: bool = True


class TempFileUploadResponse(SQLModel):
    file_id: UUID
    original_filename: str
    original_size: int
    stored_size: int
    is_compressed: bool
    expires_at: datetime
    download_permission: str
    used_bytes: int
    remaining_bytes: int


class TempFilePublicInfo(SQLModel):
    """
    Public metadata returned without auth.
    None fields indicate file not found / expired — caller raises 404.
    """

    file_id: UUID
    original_filename: str
    original_size: int
    stored_size: int
    is_compressed: bool
    download_permission: str
    expires_at: datetime
    requires_password: bool


class StorageStatusRead(SQLModel):
    used_bytes: int
    remaining_bytes: int
    storage_cap_bytes: int


class FileReadModel(SQLModel):
    """Internal model passed between tempfs service and route handler."""

    disk_path: Path
    original_filename: str
    mime_type: str
    is_compressed: bool


# ── Media ─────────────────────────────────────────────────────────────────────


class PaginatedMedia(SQLModel):
    items: list[str]  # filenames
    total: int
    page: int
    page_size: int
    pages: int


# ── Admin write models # NOTE: Currently unused ────────────────────────────────────────────────────────


class VerifyUserModel(SQLModel):
    """Used internally when approving a pending user."""

    verified_date: date
    last_login_date: date | None
    role: MemberRoleEnum
