"""
tests/test_forum_service.py
───────────────────────────
Service-layer unit tests for ForumService.

These call the singleton directly with the test session — no HTTP.
The focus is the vote toggle/flip state machine, which is complex enough
that a bug could pass through all integration tests undetected (since
those tests only assert on `user_vote` in the response, not the underlying
vote row state or the transition logic).

Also covers the DB-level retrieval helpers that are used as building blocks
by routes but never tested in isolation.

Covers:
  vote_thread   — first upvote, first downvote, toggle (same→remove),
                  flip (up→down, down→up)
  vote_reply    — same state machine as thread votes
  get_topic     — hit and miss
  get_thread_orm — hit, miss, deleted thread still returned (route guards it)
  get_reply_orm  — hit, miss
  create_thread  — round-trip creates retrievable row
  create_reply   — round-trip with parent_reply_id
  delete_thread  — soft delete sets is_deleted
  delete_reply   — soft delete sets is_deleted
"""

from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.models import Reply, Thread, Topic, TopicGroup
from src.db.enums import MemberRoleEnum
from src.db.schemas import ReplyCreate, ThreadCreate, ThreadUpdate, ReplyUpdate
from tests.conftest import make_user
from tests.constants import TEST_BODY, TEST_REPLY_BODY, TEST_TITLE


# ── DB helpers ─────────────────────────────────────────────────────────────────


async def make_group(session: AsyncSession) -> TopicGroup:
    g = TopicGroup(name=f"g_{uuid4().hex[:6]}", display_order=0)
    session.add(g)
    await session.commit()
    await session.refresh(g)
    return g


async def make_topic(session: AsyncSession, *, is_locked: bool = False) -> Topic:
    g = await make_group(session)
    t = Topic(
        group_id=g.group_id,
        name=f"t_{uuid4().hex[:6]}",
        display_order=0,
        thread_count=0,
        reply_count=0,
        is_locked=is_locked,
    )
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


async def make_thread_orm(
    session: AsyncSession,
    *,
    topic_id,
    author_id,
    is_deleted: bool = False,
) -> Thread:
    th = Thread(
        topic_id=topic_id,
        author_id=author_id,
        title=f"Thread {uuid4().hex[:6]}",
        body=TEST_BODY,
        is_deleted=is_deleted,
    )
    session.add(th)
    await session.commit()
    await session.refresh(th)
    return th


async def make_reply_orm(
    session: AsyncSession,
    *,
    thread_id,
    author_id,
    parent_reply_id=None,
) -> Reply:
    r = Reply(
        thread_id=thread_id,
        author_id=author_id,
        body=TEST_REPLY_BODY,
        parent_reply_id=parent_reply_id,
    )
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return r


# ── vote_thread ────────────────────────────────────────────────────────────────


class TestVoteThread:
    async def test_first_upvote_sets_user_vote_true(
        self, forum_svc, session: AsyncSession
    ):
        user = await make_user(session, username="tvup1")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )

        result = await forum_svc.vote_thread(thread, user.user_id, True, session)
        assert result.user_vote is True

    async def test_first_downvote_sets_user_vote_false(
        self, forum_svc, session: AsyncSession
    ):
        user = await make_user(session, username="tvdown1")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )

        result = await forum_svc.vote_thread(thread, user.user_id, False, session)
        assert result.user_vote is False

    async def test_same_upvote_twice_removes_vote(
        self, forum_svc, session: AsyncSession
    ):
        user = await make_user(session, username="tvtoggle1")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )

        await forum_svc.vote_thread(thread, user.user_id, True, session)
        result = await forum_svc.vote_thread(thread, user.user_id, True, session)
        assert result.user_vote is None

    async def test_same_downvote_twice_removes_vote(
        self, forum_svc, session: AsyncSession
    ):
        user = await make_user(session, username="tvtoggle2")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )

        await forum_svc.vote_thread(thread, user.user_id, False, session)
        result = await forum_svc.vote_thread(thread, user.user_id, False, session)
        assert result.user_vote is None

    async def test_flip_from_up_to_down(self, forum_svc, session: AsyncSession):
        user = await make_user(session, username="tvflip1")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )

        await forum_svc.vote_thread(thread, user.user_id, True, session)
        result = await forum_svc.vote_thread(thread, user.user_id, False, session)
        assert result.user_vote is False

    async def test_flip_from_down_to_up(self, forum_svc, session: AsyncSession):
        user = await make_user(session, username="tvflip2")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )

        await forum_svc.vote_thread(thread, user.user_id, False, session)
        result = await forum_svc.vote_thread(thread, user.user_id, True, session)
        assert result.user_vote is True

    async def test_two_users_vote_independently(
        self, forum_svc, session: AsyncSession
    ):
        u1 = await make_user(session, username="tvindep1")
        u2 = await make_user(session, username="tvindep2")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=u1.user_id
        )

        r1 = await forum_svc.vote_thread(thread, u1.user_id, True, session)
        r2 = await forum_svc.vote_thread(thread, u2.user_id, False, session)

        assert r1.user_vote is True
        assert r2.user_vote is False


# ── vote_reply ─────────────────────────────────────────────────────────────────


class TestVoteReply:
    async def test_first_upvote(self, forum_svc, session: AsyncSession):
        user = await make_user(session, username="rvup1")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )
        reply = await make_reply_orm(
            session, thread_id=thread.thread_id, author_id=user.user_id
        )

        result = await forum_svc.vote_reply(reply, user.user_id, True, session)
        assert result.user_vote is True

    async def test_toggle_removes_vote(self, forum_svc, session: AsyncSession):
        user = await make_user(session, username="rvtoggle")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )
        reply = await make_reply_orm(
            session, thread_id=thread.thread_id, author_id=user.user_id
        )

        await forum_svc.vote_reply(reply, user.user_id, True, session)
        result = await forum_svc.vote_reply(reply, user.user_id, True, session)
        assert result.user_vote is None

    async def test_flip_up_to_down(self, forum_svc, session: AsyncSession):
        user = await make_user(session, username="rvflip")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )
        reply = await make_reply_orm(
            session, thread_id=thread.thread_id, author_id=user.user_id
        )

        await forum_svc.vote_reply(reply, user.user_id, True, session)
        result = await forum_svc.vote_reply(reply, user.user_id, False, session)
        assert result.user_vote is False


# ── get_topic ──────────────────────────────────────────────────────────────────


class TestGetTopic:
    async def test_hit_returns_topic(self, forum_svc, session: AsyncSession):
        topic = await make_topic(session)
        found = await forum_svc.get_topic(topic.topic_id, session)
        assert found is not None
        assert found.topic_id == topic.topic_id

    async def test_miss_returns_none(self, forum_svc, session: AsyncSession):
        found = await forum_svc.get_topic(uuid4(), session)
        assert found is None


# ── get_thread_orm / get_reply_orm ─────────────────────────────────────────────


class TestGetOrmHelpers:
    async def test_get_thread_orm_hit(self, forum_svc, session: AsyncSession):
        user = await make_user(session, username="ormthread")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )

        found = await forum_svc.get_thread_orm(thread.thread_id, session)
        assert found is not None
        assert found.thread_id == thread.thread_id

    async def test_get_thread_orm_miss(self, forum_svc, session: AsyncSession):
        found = await forum_svc.get_thread_orm(uuid4(), session)
        assert found is None

    async def test_get_thread_orm_returns_deleted_thread(
        self, forum_svc, session: AsyncSession
    ):
        """ORM helper does NOT filter deleted — the route layer is responsible."""
        user = await make_user(session, username="deletedorm")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id, is_deleted=True
        )

        found = await forum_svc.get_thread_orm(thread.thread_id, session)
        assert found is not None
        assert found.is_deleted is True

    async def test_get_reply_orm_hit(self, forum_svc, session: AsyncSession):
        user = await make_user(session, username="ormreply")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )
        reply = await make_reply_orm(
            session, thread_id=thread.thread_id, author_id=user.user_id
        )

        found = await forum_svc.get_reply_orm(reply.reply_id, session)
        assert found is not None
        assert found.reply_id == reply.reply_id

    async def test_get_reply_orm_miss(self, forum_svc, session: AsyncSession):
        found = await forum_svc.get_reply_orm(uuid4(), session)
        assert found is None


# ── create_thread / create_reply ───────────────────────────────────────────────


class TestCreateHelpers:
    async def test_create_thread_round_trip(self, forum_svc, session: AsyncSession):
        user = await make_user(session, username="createthread")
        topic = await make_topic(session)
        payload = ThreadCreate(title=TEST_TITLE, body=TEST_BODY)

        result = await forum_svc.create_thread(
            topic.topic_id, user.user_id, payload, session
        )

        assert result is not None
        assert result.title == TEST_TITLE
        assert result.author_username == user.username

    async def test_create_reply_round_trip(self, forum_svc, session: AsyncSession):
        user = await make_user(session, username="createreply")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )
        payload = ReplyCreate(body=TEST_REPLY_BODY, parent_reply_id=None)

        result = await forum_svc.create_reply(
            thread.thread_id, user.user_id, payload, session
        )

        assert result is not None
        assert result.body == TEST_REPLY_BODY
        assert result.author_username == user.username

    async def test_create_nested_reply_sets_parent(
        self, forum_svc, session: AsyncSession
    ):
        user = await make_user(session, username="nestedreply")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )
        parent = await make_reply_orm(
            session, thread_id=thread.thread_id, author_id=user.user_id
        )
        payload = ReplyCreate(body=TEST_REPLY_BODY, parent_reply_id=parent.reply_id)

        result = await forum_svc.create_reply(
            thread.thread_id, user.user_id, payload, session
        )

        assert result.parent_reply_id == parent.reply_id


# ── delete_thread / delete_reply ───────────────────────────────────────────────


class TestSoftDeletes:
    async def test_delete_thread_sets_is_deleted(
        self, forum_svc, session: AsyncSession
    ):
        user = await make_user(session, username="softdelthread")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )

        await forum_svc.delete_thread(thread, session)

        await session.refresh(thread)
        assert thread.is_deleted is True

    async def test_delete_reply_sets_is_deleted(
        self, forum_svc, session: AsyncSession
    ):
        user = await make_user(session, username="softdelreply")
        topic = await make_topic(session)
        thread = await make_thread_orm(
            session, topic_id=topic.topic_id, author_id=user.user_id
        )
        reply = await make_reply_orm(
            session, thread_id=thread.thread_id, author_id=user.user_id
        )

        await forum_svc.delete_reply(reply, session)

        await session.refresh(reply)
        assert reply.is_deleted is True
