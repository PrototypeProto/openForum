from datetime import datetime
from math import ceil
from uuid import UUID

from sqlalchemy.orm import aliased
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.models import Reply, ReplyVote, Thread, ThreadVote, Topic, TopicGroup, User
from src.db.schemas import (
    PaginatedReplies,
    PaginatedThreads,
    ReplyCreate,
    ReplyRead,
    ReplyUpdate,
    ReplyWithVote,
    ThreadCreate,
    ThreadListItem,
    ThreadRead,
    ThreadUpdate,
    ThreadWithVote,
    TopicRead,
    VoteResult,
)


class ForumService:
    """
    Handles business logic for the {/forum} route
    Only USERS+ may use this
    May be sectioned to allow subsections of users for certain topics
    """

    # # # # # # # # # # # # # # # # # # # # # # # #
    #   TOPIC Methods
    # # # # # # # # # # # # # # # # # # # # # # # #
    async def get_topic_groups(self, session: AsyncSession) -> list[TopicGroup]:
        result = await session.exec(select(TopicGroup).order_by(TopicGroup.display_order))
        return result.all()

    async def retrieve_topics(self, session: AsyncSession) -> list[TopicRead]:
        """
        Returns all topics with last_poster_username resolved.

        Resolution chain for last poster:
          Topic.last_thread_id → Thread.last_activity (reply FK)
            → Reply.author_id → User.username   (someone replied)
          If no replies on that thread yet, fall back to:
            Thread.author_id → User.username     (thread author = last poster)
          If no threads at all, last_poster_username is None.
        """
        LastThread = aliased(Thread)
        LastReply = aliased(Reply)
        ReplyAuthor = aliased(User)
        ThreadAuthor = aliased(User)

        query = (
            select(
                Topic.topic_id,
                Topic.group_id,
                Topic.name,
                Topic.description,
                Topic.icon_url,
                Topic.display_order,
                Topic.thread_count,
                Topic.reply_count,
                Topic.is_locked,
                Topic.last_activity_at,
                Topic.last_thread_id,
                # Prefer the reply author; fall back to the thread author
                func.coalesce(
                    ReplyAuthor.username,
                    ThreadAuthor.username,
                ).label("last_poster_username"),
            )
            .outerjoin(LastThread, LastThread.thread_id == Topic.last_thread_id)
            .outerjoin(LastReply, LastReply.reply_id == LastThread.last_activity)
            .outerjoin(ReplyAuthor, ReplyAuthor.user_id == LastReply.author_id)
            .outerjoin(ThreadAuthor, ThreadAuthor.user_id == LastThread.author_id)
            .order_by(Topic.group_id, Topic.display_order)
        )

        rows = (await session.exec(query)).all()

        return [
            TopicRead(
                topic_id=r.topic_id,
                group_id=r.group_id,
                name=r.name,
                description=r.description,
                icon_url=r.icon_url,
                display_order=r.display_order,
                thread_count=r.thread_count,
                reply_count=r.reply_count,
                is_locked=r.is_locked,
                last_activity_at=r.last_activity_at,
                last_thread_id=r.last_thread_id,
                last_poster_username=r.last_poster_username,
            )
            for r in rows
        ]

    async def get_topic(self, topic_id: UUID, session: AsyncSession) -> TopicRead:
        return await session.get(Topic, topic_id)

    async def get_threads(
        self,
        topic_id: UUID,
        page: int,
        page_size: int,
        session: AsyncSession,
    ) -> PaginatedThreads:
        """
        Returns a paginated list of ThreadListItem with author_username and
        last_reply_username resolved via JOINs.

        Pinned threads (non-expired) are prioritized first.
        The `last_reply_username` is pulled from the reply referenced by
        Thread.last_activity (last_reply_id FK).
        """
        AuthorUser = aliased(User)
        LastReplyAuthor = aliased(User)

        base_filter = (
            Thread.topic_id == topic_id,
            Thread.is_deleted == False,  # noqa: E712
        )

        # Count total non-deleted threads for this topic
        count_result = await session.exec(select(func.count(Thread.thread_id)).where(*base_filter))
        total = count_result.one()

        sort_cols = [Thread.is_pinned.desc(), Thread.last_activity_at.desc().nulls_last()]

        rows = (
            await session.exec(
                select(
                    Thread.thread_id,
                    Thread.title,
                    Thread.author_id,
                    AuthorUser.username.label("author_username"),
                    Thread.created_at,
                    Thread.reply_count,
                    Thread.upvote_count,
                    Thread.downvote_count,
                    Thread.is_pinned,
                    Thread.last_activity_at,
                    LastReplyAuthor.username.label("last_reply_username"),
                )
                .join(AuthorUser, AuthorUser.user_id == Thread.author_id)
                .outerjoin(Reply, Reply.reply_id == Thread.last_activity)
                .outerjoin(LastReplyAuthor, LastReplyAuthor.user_id == Reply.author_id)
                .where(*base_filter)
                .order_by(*sort_cols)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()

        items = [
            ThreadListItem(
                thread_id=r.thread_id,
                title=r.title,
                author_id=r.author_id,
                author_username=r.author_username,
                created_at=r.created_at,
                reply_count=r.reply_count,
                upvote_count=r.upvote_count,
                downvote_count=r.downvote_count,
                is_pinned=r.is_pinned,
                last_activity_at=r.last_activity_at,
                last_reply_username=r.last_reply_username,
            )
            for r in rows
        ]

        return PaginatedThreads(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=ceil(total / page_size) if total else 1,
        )

    async def get_thread(
        self, thread_id: UUID, user_id: UUID, session: AsyncSession
    ) -> ThreadWithVote | None:
        """
        Fetches a single thread with author_username resolved via JOIN.
        LEFT JOINs ThreadVote for the requesting user so user_vote is populated.
        Returns a ThreadRead (not a raw Thread ORM object).
        """
        row = (
            await session.exec(
                select(
                    Thread.thread_id,
                    Thread.topic_id,
                    Thread.author_id,
                    User.username.label("author_username"),
                    Thread.title,
                    Thread.body,
                    Thread.created_at,
                    Thread.updated_at,
                    Thread.is_pinned,
                    Thread.is_locked,
                    Thread.is_deleted,
                    Thread.reply_count,
                    Thread.upvote_count,
                    Thread.downvote_count,
                    Thread.last_activity_at,
                    ThreadVote.is_upvote.label("user_vote"),
                )
                .join(User, User.user_id == Thread.author_id)
                .outerjoin(
                    ThreadVote,
                    (ThreadVote.thread_id == Thread.thread_id) & (ThreadVote.user_id == user_id),
                )
                .where(Thread.thread_id == thread_id)
            )
        ).first()

        if not row:
            return None

        return ThreadWithVote(
            thread_id=row.thread_id,
            topic_id=row.topic_id,
            author_id=row.author_id,
            author_username=row.author_username,
            title=row.title,
            body=row.body,
            created_at=row.created_at,
            updated_at=row.updated_at,
            is_pinned=row.is_pinned,
            is_locked=row.is_locked,
            is_deleted=row.is_deleted,
            reply_count=row.reply_count,
            upvote_count=row.upvote_count,
            downvote_count=row.downvote_count,
            last_activity_at=row.last_activity_at,
            user_vote=row.user_vote,
        )

    async def get_thread_orm(self, thread_id: UUID, session: AsyncSession) -> Thread | None:
        """Returns the raw ORM Thread object — needed for mutation operations."""
        return await session.get(Thread, thread_id)

    async def create_thread(
        self, topic_id: UUID, author_id: UUID, payload: ThreadCreate, session: AsyncSession
    ) -> ThreadRead:
        thread = Thread(
            topic_id=topic_id,
            author_id=author_id,
            **payload.model_dump(),
        )
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
        # Re-fetch with JOIN to get author_username
        return await self.get_thread(thread.thread_id, author_id, session)

    async def update_thread(
        self, thread: Thread, user_id: UUID, payload: ThreadUpdate, session: AsyncSession
    ) -> ThreadRead:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(thread, field, value)
        thread.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(thread)
        return await self.get_thread(thread.thread_id, user_id, session)

    async def delete_thread(self, thread: Thread, session: AsyncSession) -> None:
        thread.is_deleted = True
        await session.commit()

    #  THREAD VOTES
    # NOTE: Consider not returning updated vote to avoid extra db access, and let the local frontend use that snapshot of data
    async def vote_thread(
        self, thread: Thread, user_id: UUID, is_upvote: bool, session: AsyncSession
    ) -> VoteResult:
        existing: ThreadVote | None = (
            await session.exec(
                select(ThreadVote)
                .where(ThreadVote.user_id == user_id)
                .where(ThreadVote.thread_id == thread.thread_id)
            )
        ).first()

        resulting_vote: bool | None = is_upvote

        # vote counts handled by triggers
        if existing:
            if existing.is_upvote == is_upvote:
                await session.delete(existing)
                resulting_vote = None
            else:
                # # flip vote
                existing.is_upvote = is_upvote
        else:
            session.add(
                ThreadVote(
                    user_id=user_id,
                    thread_id=thread.thread_id,
                    is_upvote=is_upvote,
                )
            )

        await session.commit()
        await session.refresh(thread)
        return VoteResult(
            upvote_count=thread.upvote_count,
            downvote_count=thread.downvote_count,
            user_vote=resulting_vote,
        )

    #  REPLIES
    async def get_replies(
        self,
        thread_id: UUID,
        page: int,
        page_size: int,
        user_id: UUID,
        session: AsyncSession,
    ) -> PaginatedReplies:
        """
        Returns a page of replies ordered by created_at ASC.
        reply_number is the 1-based rank across the full thread.
        author_username and parent_author_username resolved via JOINs.
        user_vote is the requesting user's current vote on each reply
        (True = upvoted, False = downvoted, None = no vote).
        """
        AuthorUser = aliased(User)
        ParentReply = aliased(Reply)
        ParentAuthorUser = aliased(User)

        count_result = await session.exec(
            select(func.count(Reply.reply_id)).where(Reply.thread_id == thread_id)
        )
        total = count_result.one()

        offset = (page - 1) * page_size
        rows = (
            await session.exec(
                select(
                    Reply.reply_id,
                    Reply.thread_id,
                    Reply.author_id,
                    AuthorUser.username.label("author_username"),
                    Reply.parent_reply_id,
                    ParentAuthorUser.username.label("parent_author_username"),
                    Reply.body,
                    Reply.is_deleted,
                    Reply.created_at,
                    Reply.updated_at,
                    Reply.upvote_count,
                    Reply.downvote_count,
                    ReplyVote.is_upvote.label("user_vote"),
                )
                .join(AuthorUser, AuthorUser.user_id == Reply.author_id)
                .outerjoin(ParentReply, ParentReply.reply_id == Reply.parent_reply_id)
                .outerjoin(ParentAuthorUser, ParentAuthorUser.user_id == ParentReply.author_id)
                .outerjoin(
                    ReplyVote,
                    (ReplyVote.reply_id == Reply.reply_id) & (ReplyVote.user_id == user_id),
                )
                .where(Reply.thread_id == thread_id)
                .order_by(Reply.created_at.asc())
                .offset(offset)
                .limit(page_size)
            )
        ).all()

        items = [
            ReplyWithVote(
                reply_id=r.reply_id,
                thread_id=r.thread_id,
                author_id=r.author_id,
                author_username=r.author_username,
                parent_reply_id=r.parent_reply_id,
                parent_author_username=r.parent_author_username,
                body=r.body,
                is_deleted=r.is_deleted,
                created_at=r.created_at,
                updated_at=r.updated_at,
                reply_number=offset + idx + 1,
                upvote_count=r.upvote_count,
                downvote_count=r.downvote_count,
                user_vote=r.user_vote,  # None when no ReplyVote row matched
            )
            for idx, r in enumerate(rows)
        ]

        return PaginatedReplies(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=ceil(total / page_size) if total else 1,
        )

    async def get_reply_children(self, reply_id: UUID, session: AsyncSession) -> list[ReplyRead]:
        """
        Fetch immediate children of a reply (one level deep).
        author_username and parent_author_username resolved via JOINs.
        reply_number is not meaningful for nested children, set to 0.
        """
        AuthorUser = aliased(User)
        ParentReply = aliased(Reply)
        ParentAuthorUser = aliased(User)

        rows = (
            await session.exec(
                select(
                    Reply.reply_id,
                    Reply.thread_id,
                    Reply.author_id,
                    AuthorUser.username.label("author_username"),
                    Reply.parent_reply_id,
                    ParentAuthorUser.username.label("parent_author_username"),
                    Reply.body,
                    Reply.is_deleted,
                    Reply.created_at,
                    Reply.updated_at,
                    Reply.upvote_count,
                    Reply.downvote_count,
                )
                .join(AuthorUser, AuthorUser.user_id == Reply.author_id)
                .outerjoin(ParentReply, ParentReply.reply_id == Reply.parent_reply_id)
                .outerjoin(ParentAuthorUser, ParentAuthorUser.user_id == ParentReply.author_id)
                .where(Reply.parent_reply_id == reply_id)
                .order_by(Reply.created_at.asc())
            )
        ).all()

        return [
            ReplyRead(
                reply_id=r.reply_id,
                thread_id=r.thread_id,
                author_id=r.author_id,
                author_username=r.author_username,
                parent_reply_id=r.parent_reply_id,
                parent_author_username=r.parent_author_username,
                body=r.body,
                is_deleted=r.is_deleted,
                created_at=r.created_at,
                updated_at=r.updated_at,
                reply_number=0,
                upvote_count=r.upvote_count,
                downvote_count=r.downvote_count,
            )
            for r in rows
        ]

    async def get_reply_orm(self, reply_id: UUID, session: AsyncSession) -> Reply | None:
        """Returns raw ORM Reply — used for mutation guards (is_deleted check, author check)."""
        return await session.get(Reply, reply_id)

    async def get_reply(self, reply_id: UUID, session: AsyncSession) -> ReplyRead | None:
        """Single reply with author_username resolved via JOIN."""
        AuthorUser = aliased(User)
        ParentReply = aliased(Reply)
        ParentAuthorUser = aliased(User)

        row = (
            await session.exec(
                select(
                    Reply.reply_id,
                    Reply.thread_id,
                    Reply.author_id,
                    AuthorUser.username.label("author_username"),
                    Reply.parent_reply_id,
                    ParentAuthorUser.username.label("parent_author_username"),
                    Reply.body,
                    Reply.is_deleted,
                    Reply.created_at,
                    Reply.updated_at,
                    Reply.upvote_count,
                    Reply.downvote_count,
                )
                .join(AuthorUser, AuthorUser.user_id == Reply.author_id)
                .outerjoin(ParentReply, ParentReply.reply_id == Reply.parent_reply_id)
                .outerjoin(ParentAuthorUser, ParentAuthorUser.user_id == ParentReply.author_id)
                .where(Reply.reply_id == reply_id)
            )
        ).first()

        if not row:
            return None

        return ReplyRead(
            reply_id=row.reply_id,
            thread_id=row.thread_id,
            author_id=row.author_id,
            author_username=row.author_username,
            parent_reply_id=row.parent_reply_id,
            parent_author_username=row.parent_author_username,
            body=row.body,
            is_deleted=row.is_deleted,
            created_at=row.created_at,
            updated_at=row.updated_at,
            reply_number=0,
            upvote_count=row.upvote_count,
            downvote_count=row.downvote_count,
        )

    async def create_reply(
        self,
        thread_id: UUID,
        author_id: UUID,
        payload: ReplyCreate,
        session: AsyncSession,
    ) -> ReplyRead:
        reply = Reply(thread_id=thread_id, author_id=author_id, **payload.model_dump())
        session.add(reply)
        await session.commit()
        await session.refresh(reply)
        # Re-fetch with JOINs
        # children = await self.get_reply_children(reply.parent_reply_id or reply.reply_id, session)
        # Simpler: just build a minimal ReplyRead from the refresh
        author = await session.get(User, author_id)
        return ReplyRead(
            reply_id=reply.reply_id,
            thread_id=reply.thread_id,
            author_id=reply.author_id,
            author_username=author.username if author else "",
            parent_reply_id=reply.parent_reply_id,
            parent_author_username=None,
            body=reply.body,
            is_deleted=reply.is_deleted,
            created_at=reply.created_at,
            updated_at=reply.updated_at,
            reply_number=0,  # caller can recompute from page context
            upvote_count=reply.upvote_count,
            downvote_count=reply.downvote_count,
        )

    async def update_reply(
        self, reply: Reply, payload: ReplyUpdate, session: AsyncSession
    ) -> ReplyRead | None:
        reply.body = payload.body
        reply.updated_at = datetime.utcnow()
        await session.commit()
        # await session.refresh(reply)
        return await self.get_reply(reply.reply_id, session)

    async def delete_reply(self, reply: Reply, session: AsyncSession) -> None:
        reply.is_deleted = True
        await session.commit()

    #  REPLY VOTES

    async def vote_reply(
        self, reply: Reply, user_id: UUID, is_upvote: bool, session: AsyncSession
    ) -> VoteResult:
        existing = (
            await session.exec(
                select(ReplyVote)
                .where(ReplyVote.user_id == user_id)
                .where(ReplyVote.reply_id == reply.reply_id)
            )
        ).first()

        resulting_vote: bool | None = is_upvote

        if existing:
            if existing.is_upvote == is_upvote:
                await session.delete(existing)
                resulting_vote = None
            else:
                # if is_upvote:
                #     reply.upvote_count += 1
                #     reply.downvote_count = max(0, reply.downvote_count - 1)
                # else:
                #     reply.downvote_count += 1
                #     reply.upvote_count = max(0, reply.upvote_count - 1)
                existing.is_upvote = is_upvote
        else:
            session.add(
                ReplyVote(
                    user_id=user_id,
                    reply_id=reply.reply_id,
                    is_upvote=is_upvote,
                )
            )

        await session.commit()
        await session.refresh(reply)
        return VoteResult(
            upvote_count=reply.upvote_count,
            downvote_count=reply.downvote_count,
            user_vote=resulting_vote,
        )

    async def get_user_reply_vote(
        self, reply_id: UUID, user_id: UUID, session: AsyncSession
    ) -> bool | None:
        vote = (
            await session.exec(
                select(ReplyVote)
                .where(ReplyVote.user_id == user_id)
                .where(ReplyVote.reply_id == reply_id)
            )
        ).first()
        return vote.is_upvote if vote else None


# ---------------------------------------------------------------------------
# Module-level singleton — import this instead of instantiating ForumService()
# ---------------------------------------------------------------------------

forum_service = ForumService()
