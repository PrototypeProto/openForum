from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import Session, select, func
from typing import Optional, Annotated
from datetime import datetime
from .service import ForumService
from src.db.read_models import *
from src.admin.service import AdminService
from src.db.models import User
from src.auth.dependencies import access_token_bearer
from src.auth.service import AuthService
from src.db.main import get_session

router = APIRouter(prefix="/forum", tags=["forum"], dependencies=[access_token_bearer])
service = ForumService()
auth_service = AuthService()
admin_service = AdminService()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]

# TOPIC GROUPS
@router.get("/groups", response_model=list[TopicGroupRead])
async def list_topic_groups(session: SessionDependency):
    """
    GET /forum/groups
    Returns all topic groups ordered by display_order.
    Used by the forum index to build the top-level category cards.
    """
    return await service.get_topic_groups(session)


# TOPICS
@router.get("/topics", response_model=list[TopicRead])
async def list_topics(
    session: SessionDependency,
    group_id: Optional[UUID] = Query(None),
):
    """
    GET /forum/topics?group_id=<uuid>  (group_id optional)
    Returns all topics (optionally filtered by group) with thread/reply counts
    and last-activity info for the forum index sidebar.
    Prefer fetching without group_id to avoid N calls on the index page.
    """
    return await service.retrieve_topics(group_id, session)





# THREADS
# NOTE: dont plan on using top/oldest
@router.get("/topics/{topic_id}/threads", response_model=PaginatedThreads)
async def list_threads(
    topic_id: UUID,
    session: SessionDependency,
    page: int = Query(1, ge=1),
):
    """
    GET /forum/topics/{topic_id}/threads?page=1
    Paginated thread listing ordered by last_activity_at desc.
    Pinned (non-expired) threads float to the top on page 1 only.
    page 1 → page_size 14  (reserves visual slot for the pinned-thread header)
    page 2+ → page_size 15
    """
    page_size = 15 if page > 1 else 14

    topic = await service.get_topic(topic_id, session)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    return await service.get_threads(topic_id, page, page_size, session)

@router.get("/threads/{thread_id}", response_model=ThreadRead)
async def get_thread(thread_id: UUID, session: SessionDependency):
    """
    GET /forum/threads/{thread_id}
    Returns full thread detail with author_username resolved.
    """
    thread = await service.get_thread(thread_id, session)
    if not thread or thread.is_deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
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
    token_details: dict = access_token_bearer,
):
    """
    POST /forum/topics/{topic_id}/threads
    Creates a new thread. Returns the created thread with author_username.
    """
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid permissions")

    topic = await service.get_topic(topic_id, session)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.is_locked:
        raise HTTPException(status_code=403, detail="Topic is locked")

    author_id = UUID(token_details["user"]["user_id"])
    return await service.create_thread(topic_id, author_id, payload, session)


@router.patch("/threads/{thread_id}", response_model=ThreadRead)
async def update_thread(
    thread_id: UUID,
    payload: ThreadUpdate,
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    """
    PATCH /forum/threads/{thread_id}
    Author or admin can edit body/title.
    Only admins may change is_pinned / pin_expires_at / is_locked.
    """
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid permissions")

    # Use ORM object for mutation
    thread = await service.get_thread_orm(thread_id, session)
    if not thread or thread.is_deleted:
        raise HTTPException(status_code=404, detail="Thread not found")

    user_id = UUID(token_details["user"]["user_id"])
    is_author = thread.author_id == user_id
    is_admin = await admin_service.verify_admin(token_details, session)

    if not is_author and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    mod_only_fields = {"is_pinned", "pin_expires_at", "is_locked"}
    if any(f in payload.model_dump(exclude_unset=True) for f in mod_only_fields) and not is_admin:
        raise HTTPException(status_code=403, detail="Only moderators can pin or lock threads")

    return await service.update_thread(thread, payload, session)


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: UUID,
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    """
    DELETE /forum/threads/{thread_id}
    Soft-delete. Author or admin only.
    """
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid permissions")

    thread = await service.get_thread_orm(thread_id, session)
    if not thread or thread.is_deleted:
        raise HTTPException(status_code=404, detail="Thread not found")

    user_id = UUID(token_details["user"]["user_id"])
    is_author = thread.author_id == user_id
    is_admin = await admin_service.verify_admin(token_details, session)

    if not is_author and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    await service.delete_thread(thread, session)


# THREAD VOTES

@router.post("/threads/{thread_id}/vote", response_model=VoteResult)
async def vote_thread(
    thread_id: UUID,
    is_upvote: bool,
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    """
    POST /forum/threads/{thread_id}/vote  { is_upvote: bool }
    Cast or toggle a vote on a thread.
    Sending the same vote twice removes it. Returns updated counts + resulting vote state.
    """
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid permissions")

    thread = await service.get_thread_orm(thread_id, session)
    if not thread or thread.is_deleted:
        raise HTTPException(status_code=404, detail="Thread not found")

    user_id = UUID(token_details["user"]["user_id"])
    return await service.vote_thread(thread, user_id, is_upvote, session)



# REPLIES

@router.get("/threads/{thread_id}/replies", response_model=PaginatedReplies)
async def list_replies(
    thread_id: UUID,
    session: SessionDependency,
    page: int = Query(1, ge=1),
    token_details: dict = access_token_bearer,
):
    """
    GET /forum/threads/{thread_id}/replies?page=1
    Paginated top-level replies ordered by created_at ASC.
    reply_number reflects the 1-based creation rank across the full thread.
    page 1 → page_size 14  (the thread body occupies logical slot #1 in the UI)
    page 2+ → page_size 15
    Nested children are fetched separately via GET /replies/{reply_id}/children.
    """
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid permissions")

    page_size: int = 14 if page == 1 else 15

    thread = await service.get_thread_orm(thread_id, session)
    if not thread or thread.is_deleted:
        raise HTTPException(status_code=404, detail="Thread not found")

    return await service.get_replies(thread_id, page, page_size, session)

@router.get("/replies/{reply_id}/parent", response_model=ReplyRead)
async def get_reply_parent(
    reply_id: UUID,
    session: SessionDependency,
):
    """
    GET /forum/replies/{reply_id}/parent
    Fetches the parent reply for a given reply, used to render the
    'replying to' context block when the parent is not in the current page.
    Returns 404 if the reply has no parent (is a top-level reply).
    """
    reply = await service.get_reply_orm(reply_id, session)
    if not reply or not reply.parent_reply_id:
        raise HTTPException(status_code=404, detail="No parent reply")
    return await service.get_reply(reply.parent_reply_id, session)

# @router.get("/replies/{reply_id}/children", response_model=list[ReplyRead])
# async def get_reply_children(
#     reply_id: UUID,
#     session: SessionDependency,
# ):
#     """
#     NOTE: this is for reddit-style comments
#     GET /forum/replies/{reply_id}/children
#     Fetches immediate nested replies for a parent reply (one level at a time).
#     Used to lazily load sub-replies when the user clicks 'reply to' context.
#     """
#     return await service.get_reply_children(reply_id, session)


@router.post(
    "/threads/{thread_id}/replies",
    response_model=ReplyRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_reply(
    thread_id: UUID,
    payload: ReplyCreate,
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    """
    POST /forum/threads/{thread_id}/replies  { body, parent_reply_id? }
    Creates a reply (or a nested reply if parent_reply_id is provided).
    Validates that parent_reply belongs to the same thread.
    """
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid permissions")

    thread = await service.get_thread_orm(thread_id, session)
    if not thread or thread.is_deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.is_locked:
        raise HTTPException(status_code=403, detail="Thread is locked")

    if payload.parent_reply_id:
        parent = await service.get_reply_orm(payload.parent_reply_id, session)
        if not parent or parent.thread_id != thread_id:
            raise HTTPException(status_code=400, detail="Invalid parent reply")

    author_id = UUID(token_details["user"]["user_id"])
    return await service.create_reply(thread_id, author_id, payload, session)


@router.patch("/replies/{reply_id}", response_model=ReplyRead)
async def update_reply(
    reply_id: UUID,
    payload: ReplyUpdate,
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    """
    PATCH /forum/replies/{reply_id}  { body }
    Author-only. Only the body is editable; updated_at is stamped automatically.
    """
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid permissions")

    reply = await service.get_reply_orm(reply_id, session)
    if not reply or reply.is_deleted:
        raise HTTPException(status_code=404, detail="Reply not found")

    user_id = UUID(token_details["user"]["user_id"])
    if reply.author_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return await service.update_reply(reply, payload, session)


@router.delete("/replies/{reply_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reply(
    reply_id: UUID,
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    """
    DELETE /forum/replies/{reply_id}
    Soft-delete. Keeps the row so nested replies retain their parent reference.
    Author or admin only.
    """
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid permissions")

    reply = await service.get_reply_orm(reply_id, session)
    if not reply or reply.is_deleted:
        raise HTTPException(status_code=404, detail="Reply not found")

    user_id = UUID(token_details["user"]["user_id"])
    is_author = reply.author_id == user_id
    is_admin = await admin_service.verify_admin(token_details, session)

    if not is_author and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    await service.delete_reply(reply, session)


# REPLY VOTES
@router.post("/replies/{reply_id}/vote", response_model=VoteResult)
async def vote_reply(
    reply_id: UUID,
    payload: VotePayload,
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    """
    POST /forum/replies/{reply_id}/vote  { payload: VotePayload }
    Same toggle/flip logic as thread votes.
    Returns updated counts + resulting vote state.
    """
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid permissions")

    reply = await service.get_reply_orm(reply_id, session)
    if not reply or reply.is_deleted:
        raise HTTPException(status_code=404, detail="Reply not found")

    user_id = UUID(token_details["user"]["user_id"])
    return await service.vote_reply(reply, user_id, payload.is_upvote, session)




