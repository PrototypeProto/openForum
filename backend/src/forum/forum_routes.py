from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.admin.service import admin_service
from src.auth.csrf import require_csrf
from src.auth.dependencies import require_user
from src.db.main import get_session
from src.db.schemas import (
    PaginatedReplies,
    PaginatedThreads,
    ReplyCreate,
    ReplyRead,
    ReplyUpdate,
    ThreadCreate,
    ThreadRead,
    ThreadUpdate,
    ThreadWithVote,
    TopicGroupRead,
    TopicRead,
    VotePayload,
    VoteResult,
)
from src.exceptions import (
    BadRequestError,
    ForbiddenError,
    LockedError,
    NotFoundError,
)
from src.rate_limit import rate_limit

from .service import forum_service as service

router = APIRouter(prefix="/forum", tags=["forum"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/groups", response_model=list[TopicGroupRead])
async def list_topic_groups(
    session: SessionDependency,
    token_details: dict = require_user,
):
    return await service.get_topic_groups(session)


@router.get("/topics", response_model=list[TopicRead])
async def list_topics(
    session: SessionDependency,
    token_details: dict = require_user,
):
    return await service.retrieve_topics(session)


@router.get("/topics/{topic_id}/threads", response_model=PaginatedThreads)
async def list_topic_threads(
    topic_id: UUID,
    session: SessionDependency,
    page: int = Query(1, ge=1),
    token_details: dict = require_user,
):
    topic = await service.get_topic(topic_id, session)
    if not topic:
        raise NotFoundError("Topic not found")

    return await service.get_threads(topic_id, page, 15, session)


@router.get("/threads/{thread_id}", response_model=ThreadWithVote)
async def get_thread_info(
    thread_id: UUID,
    session: SessionDependency,
    token_details: dict = require_user,
):
    thread = await service.get_thread(thread_id, UUID(token_details["user"]["user_id"]), session)
    if not thread or thread.is_deleted:
        raise NotFoundError("Thread not found")
    return thread


@router.post(
    "/topics/{topic_id}/threads",
    response_model=ThreadRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_thread(
    topic_id: UUID,
    payload: ThreadCreate,
    session: SessionDependency,
    token_details: dict = require_user,
    _rl: None = rate_limit("forum:thread:create", limit=10, window=60),
    _csrf: None = require_csrf,
):
    topic = await service.get_topic(topic_id, session)
    if not topic:
        raise NotFoundError("Topic not found")
    if topic.is_locked:
        raise LockedError("Topic is locked")

    author_id = UUID(token_details["user"]["user_id"])
    return await service.create_thread(topic_id, author_id, payload, session)


@router.patch("/threads/{thread_id}", response_model=ThreadRead)
async def update_thread(
    thread_id: UUID,
    payload: ThreadUpdate,
    session: SessionDependency,
    token_details: dict = require_user,
    _csrf: None = require_csrf,
):
    thread = await service.get_thread_orm(thread_id, session)
    if not thread or thread.is_deleted:
        raise NotFoundError("Thread not found")

    user_id = UUID(token_details["user"]["user_id"])
    is_author = thread.author_id == user_id
    is_admin = await admin_service.is_user_admin(token_details["user"]["username"], session)

    if not is_author and not is_admin:
        raise ForbiddenError()

    mod_only_fields = {"is_pinned", "pin_expires_at", "is_locked"}
    if any(f in payload.model_dump(exclude_unset=True) for f in mod_only_fields) and not is_admin:
        raise ForbiddenError("Only moderators can pin or lock threads")

    return await service.update_thread(thread, user_id, payload, session)


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: UUID,
    session: SessionDependency,
    token_details: dict = require_user,
    _csrf: None = require_csrf,
):
    thread = await service.get_thread_orm(thread_id, session)
    if not thread or thread.is_deleted:
        raise NotFoundError("Thread not found")

    user_id = UUID(token_details["user"]["user_id"])
    is_author = thread.author_id == user_id
    is_admin = await admin_service.is_user_admin(token_details["user"]["username"], session)

    if not is_author and not is_admin:
        raise ForbiddenError()

    await service.delete_thread(thread, session)


@router.post("/threads/{thread_id}/vote", response_model=VoteResult)
async def vote_thread(
    thread_id: UUID,
    payload: Annotated[VotePayload, Body()],
    session: SessionDependency,
    token_details: dict = require_user,
    _rl: None = rate_limit("forum:vote", limit=30, window=60),
    _csrf: None = require_csrf,
):
    thread = await service.get_thread_orm(thread_id, session)
    if not thread or thread.is_deleted:
        raise NotFoundError("Thread not found")

    return await service.vote_thread(
        thread, UUID(token_details["user"]["user_id"]), payload.is_upvote, session
    )


@router.get("/threads/{thread_id}/replies", response_model=PaginatedReplies)
async def list_replies(
    thread_id: UUID,
    session: SessionDependency,
    page: int = Query(1, ge=1),
    token_details: dict = require_user,
):
    thread = await service.get_thread_orm(thread_id, session)
    if not thread or thread.is_deleted:
        raise NotFoundError("Thread not found")

    return await service.get_replies(thread_id, page, 15, token_details["user"]["user_id"], session)


@router.get("/replies/{reply_id}/parent", response_model=ReplyRead)
async def get_reply_parent(
    reply_id: UUID,
    session: SessionDependency,
    token_details: dict = require_user,
):
    reply = await service.get_reply_orm(reply_id, session)
    if not reply or not reply.parent_reply_id:
        raise NotFoundError("No parent reply")
    return await service.get_reply(reply.parent_reply_id, session)


@router.post(
    "/threads/{thread_id}/replies",
    response_model=ReplyRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_reply(
    thread_id: UUID,
    payload: ReplyCreate,
    session: SessionDependency,
    token_details: dict = require_user,
    _rl: None = rate_limit("forum:reply:create", limit=20, window=60),
    _csrf: None = require_csrf,
):
    thread = await service.get_thread_orm(thread_id, session)
    if not thread or thread.is_deleted:
        raise NotFoundError("Thread not found")
    if thread.is_locked:
        raise LockedError("Thread is locked")

    if payload.parent_reply_id:
        parent = await service.get_reply_orm(payload.parent_reply_id, session)
        if not parent or parent.thread_id != thread_id:
            raise BadRequestError("Invalid parent reply")

    author_id = UUID(token_details["user"]["user_id"])
    return await service.create_reply(thread_id, author_id, payload, session)


@router.patch("/replies/{reply_id}", response_model=ReplyRead)
async def update_reply(
    reply_id: UUID,
    payload: ReplyUpdate,
    session: SessionDependency,
    token_details: dict = require_user,
    _csrf: None = require_csrf,
):
    reply = await service.get_reply_orm(reply_id, session)
    if not reply or reply.is_deleted:
        raise NotFoundError("Reply not found")

    if reply.author_id != UUID(token_details["user"]["user_id"]):
        raise ForbiddenError()

    return await service.update_reply(reply, payload, session)


@router.delete("/replies/{reply_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reply(
    reply_id: UUID,
    session: SessionDependency,
    token_details: dict = require_user,
    _csrf: None = require_csrf,
):
    reply = await service.get_reply_orm(reply_id, session)
    if not reply or reply.is_deleted:
        raise NotFoundError("Reply not found")

    user_id = UUID(token_details["user"]["user_id"])
    is_author = reply.author_id == user_id
    is_admin = await admin_service.is_user_admin(token_details["user"]["username"], session)

    if not is_author and not is_admin:
        raise ForbiddenError()

    await service.delete_reply(reply, session)


@router.post("/replies/{reply_id}/vote", response_model=VoteResult)
async def vote_reply(
    reply_id: UUID,
    payload: Annotated[VotePayload, Body()],
    session: SessionDependency,
    token_details: dict = require_user,
    _rl: None = rate_limit("forum:vote", limit=30, window=60),
    _csrf: None = require_csrf,
):
    reply = await service.get_reply_orm(reply_id, session)
    if not reply or reply.is_deleted:
        raise NotFoundError("Reply not found")

    return await service.vote_reply(
        reply, UUID(token_details["user"]["user_id"]), payload.is_upvote, session
    )
