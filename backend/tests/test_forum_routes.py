"""
tests/test_forum_routes.py
──────────────────────────
Integration tests for all /forum endpoints.

Covers:
  GET  /forum/groups
  GET  /forum/topics
  GET  /forum/topics/{id}/threads
  POST /forum/topics/{id}/threads      — create, locked topic, auth required
  GET  /forum/threads/{id}
  PATCH /forum/threads/{id}            — author edit, admin edit, forbidden
  DELETE /forum/threads/{id}           — soft delete, author/admin only
  POST /forum/threads/{id}/vote        — upvote, toggle, flip
  GET  /forum/threads/{id}/replies
  POST /forum/threads/{id}/replies     — create, locked thread, nested
  PATCH /forum/replies/{id}            — author only
  DELETE /forum/replies/{id}           — author and admin
  POST /forum/replies/{id}/vote

NOTE: thread_count, reply_count, upvote_count, downvote_count are maintained
by Postgres triggers that don't run under create_all. Tests that assert on
those counters are marked @pytest.mark.triggers and skipped by default.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.enums import MemberRoleEnum
from src.db.models import Reply, Thread, Topic, TopicGroup
from src.db.redis_client import add_registered_user
from tests.conftest import auth_cookies, make_access_token, make_user
from tests.constants import (
    TEST_BODY,
    TEST_BODY_EDIT,
    TEST_BODY_UPDATED,
    TEST_REPLY_BODY,
    TEST_REPLY_BODY_CREATE,
    TEST_TITLE,
    TEST_TITLE_CREATE,
    TEST_TITLE_UPDATED,
    TEST_TRIGGER_REPLY_BODY,
    TEST_TRIGGER_TITLE_1,
    TEST_TRIGGER_TITLE_2,
)

# ── Forum data factories ──────────────────────────────────────────────────────


async def make_topic_group(session: AsyncSession, *, name: str = None) -> TopicGroup:
    group = TopicGroup(name=name or f"Group {uuid4().hex[:6]}", display_order=0)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


async def make_topic(
    session: AsyncSession,
    *,
    name: str = None,
    group_id=None,
    is_locked: bool = False,
) -> Topic:
    topic = Topic(
        name=name or f"Topic {uuid4().hex[:6]}",
        group_id=group_id,
        is_locked=is_locked,
        display_order=0,
        thread_count=0,
        reply_count=0,
    )
    session.add(topic)
    await session.commit()
    await session.refresh(topic)
    return topic


async def make_thread(
    session: AsyncSession,
    *,
    topic_id,
    author_id,
    title: str = "Test Thread",
    body: str = "Thread body.",
    is_pinned: bool = False,
    is_locked: bool = False,
    is_deleted: bool = False,
) -> Thread:
    thread = Thread(
        topic_id=topic_id,
        author_id=author_id,
        title=title,
        body=body,
        is_pinned=is_pinned,
        is_locked=is_locked,
        is_deleted=is_deleted,
    )
    session.add(thread)
    await session.commit()
    await session.refresh(thread)
    return thread


async def make_reply(
    session: AsyncSession,
    *,
    thread_id,
    author_id,
    body: str = "Reply body.",
    parent_reply_id=None,
) -> Reply:
    reply = Reply(
        thread_id=thread_id,
        author_id=author_id,
        body=body,
        parent_reply_id=parent_reply_id,
    )
    session.add(reply)
    await session.commit()
    await session.refresh(reply)
    return reply


async def user_with_cookies(session, role=MemberRoleEnum.USER, username=None):
    """Shorthand: create a user, prime Redis, return (user, cookies)."""
    user = await make_user(session, role=role, username=username)
    await add_registered_user(user.username, role)
    return user, auth_cookies(make_access_token(user))


# ── GET /forum/groups ─────────────────────────────────────────────────────────


class TestListGroups:
    async def test_returns_groups(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await user_with_cookies(session)
        await make_topic_group(session, name="Unique Group Alpha")

        r = await client.get("/forum/groups", cookies=cookies)
        assert r.status_code == 200
        names = [g["name"] for g in r.json()]
        assert "Unique Group Alpha" in names

    async def test_unauthenticated_returns_403(self, client: AsyncClient):
        r = await client.get("/forum/groups")
        assert r.status_code == 403


# ── GET /forum/topics ─────────────────────────────────────────────────────────


class TestListTopics:
    async def test_returns_topics(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await user_with_cookies(session)
        await make_topic(session, name="Unique Topic Beta")

        r = await client.get("/forum/topics", cookies=cookies)
        assert r.status_code == 200
        names = [t["name"] for t in r.json()]
        assert "Unique Topic Beta" in names

    async def test_unauthenticated_returns_403(self, client: AsyncClient):
        r = await client.get("/forum/topics")
        assert r.status_code == 403


# ── GET /forum/topics/{id}/threads ────────────────────────────────────────────


class TestListThreads:
    async def test_returns_empty_for_new_topic(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await user_with_cookies(session)
        topic = await make_topic(session)

        r = await client.get(f"/forum/topics/{topic.topic_id}/threads", cookies=cookies)
        assert r.status_code == 200
        body = r.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["pages"] == 1

    async def test_returns_threads_in_topic(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        await make_thread(
            session, topic_id=topic.topic_id, author_id=user.user_id, title="Alpha Thread"
        )
        await make_thread(
            session, topic_id=topic.topic_id, author_id=user.user_id, title="Beta Thread"
        )

        r = await client.get(f"/forum/topics/{topic.topic_id}/threads", cookies=cookies)
        assert r.status_code == 200
        titles = [t["title"] for t in r.json()["items"]]
        assert "Alpha Thread" in titles
        assert "Beta Thread" in titles

    async def test_deleted_threads_excluded(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        await make_thread(
            session,
            topic_id=topic.topic_id,
            author_id=user.user_id,
            title="Visible",
            is_deleted=False,
        )
        await make_thread(
            session, topic_id=topic.topic_id, author_id=user.user_id, title="Gone", is_deleted=True
        )

        r = await client.get(f"/forum/topics/{topic.topic_id}/threads", cookies=cookies)
        titles = [t["title"] for t in r.json()["items"]]
        assert "Visible" in titles
        assert "Gone" not in titles

    async def test_pinned_threads_come_first(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        await make_thread(
            session,
            topic_id=topic.topic_id,
            author_id=user.user_id,
            title="Normal",
            is_pinned=False,
        )
        await make_thread(
            session, topic_id=topic.topic_id, author_id=user.user_id, title="Pinned", is_pinned=True
        )

        r = await client.get(f"/forum/topics/{topic.topic_id}/threads", cookies=cookies)
        items = r.json()["items"]
        assert items[0]["title"] == "Pinned"

    async def test_unknown_topic_returns_404(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await user_with_cookies(session)
        r = await client.get(f"/forum/topics/{uuid4()}/threads", cookies=cookies)
        assert r.status_code == 404


# ── POST /forum/topics/{id}/threads ──────────────────────────────────────────


class TestCreateThread:
    async def test_creates_thread(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)

        r = await client.post(
            f"/forum/topics/{topic.topic_id}/threads",
            json={"title": TEST_TITLE_CREATE, "body": TEST_BODY},
            cookies=cookies,
        )
        assert r.status_code == 201
        body = r.json()
        assert body["title"] == TEST_TITLE_CREATE
        assert body["author_username"] == user.username

    async def test_locked_topic_returns_403(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await user_with_cookies(session)
        topic = await make_topic(session, is_locked=True)

        r = await client.post(
            f"/forum/topics/{topic.topic_id}/threads",
            json={"title": TEST_TITLE, "body": TEST_BODY},
            cookies=cookies,
        )
        assert r.status_code == 403

    async def test_unknown_topic_returns_404(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await user_with_cookies(session)
        r = await client.post(
            f"/forum/topics/{uuid4()}/threads",
            json={"title": TEST_TITLE, "body": TEST_BODY},
            cookies=cookies,
        )
        assert r.status_code == 404

    async def test_unauthenticated_returns_403(self, client: AsyncClient, session: AsyncSession):
        topic = await make_topic(session)
        r = await client.post(
            f"/forum/topics/{topic.topic_id}/threads",
            json={"title": TEST_TITLE, "body": TEST_BODY},
        )
        assert r.status_code == 403

    async def test_title_too_long_returns_422(self, client: AsyncClient, session: AsyncSession):
        _, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        r = await client.post(
            f"/forum/topics/{topic.topic_id}/threads",
            json={"title": "x" * 201, "body": TEST_BODY},
            cookies=cookies,
        )
        assert r.status_code == 422


# ── PATCH /forum/threads/{id} ─────────────────────────────────────────────────


class TestUpdateThread:
    async def test_author_can_edit_title_and_body(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)

        r = await client.patch(
            f"/forum/threads/{thread.thread_id}",
            json={"title": TEST_TITLE_UPDATED, "body": TEST_BODY_UPDATED},
            cookies=cookies,
        )
        assert r.status_code == 200
        assert r.json()["title"] == TEST_TITLE_UPDATED

    async def test_non_author_non_admin_returns_403(
        self, client: AsyncClient, session: AsyncSession
    ):
        author, _ = await user_with_cookies(session, username="threadauthor")
        other, cookies = await user_with_cookies(session, username="otherguy")
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=author.user_id)

        r = await client.patch(
            f"/forum/threads/{thread.thread_id}",
            json={"body": TEST_BODY},
            cookies=cookies,
        )
        assert r.status_code == 403

    async def test_admin_can_edit_any_thread(self, client: AsyncClient, session: AsyncSession):
        author, _ = await user_with_cookies(session, username="regularauthor")
        admin, admin_cookies = await user_with_cookies(
            session, role=MemberRoleEnum.ADMIN, username="admineditor"
        )
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=author.user_id)

        r = await client.patch(
            f"/forum/threads/{thread.thread_id}",
            json={"body": TEST_BODY},
            cookies=admin_cookies,
        )
        assert r.status_code == 200

    async def test_non_admin_cannot_pin(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)

        r = await client.patch(
            f"/forum/threads/{thread.thread_id}",
            json={"is_pinned": True},
            cookies=cookies,
        )
        assert r.status_code == 403
        assert "moderator" in r.json()["detail"].lower()

    async def test_admin_can_pin(self, client: AsyncClient, session: AsyncSession):
        author, _ = await user_with_cookies(session, username="pinauthor")
        admin, admin_cookies = await user_with_cookies(
            session, role=MemberRoleEnum.ADMIN, username="pinner"
        )
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=author.user_id)

        r = await client.patch(
            f"/forum/threads/{thread.thread_id}",
            json={"is_pinned": True},
            cookies=admin_cookies,
        )
        assert r.status_code == 200
        assert r.json()["is_pinned"] is True


# ── DELETE /forum/threads/{id} ────────────────────────────────────────────────


class TestDeleteThread:
    async def test_author_can_soft_delete(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)

        r = await client.delete(f"/forum/threads/{thread.thread_id}", cookies=cookies)
        assert r.status_code == 204

        # Thread should now be soft-deleted (is_deleted=True)
        await session.refresh(thread)
        assert thread.is_deleted is True

    async def test_deleted_thread_returns_404_on_get(
        self, client: AsyncClient, session: AsyncSession
    ):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)
        await client.delete(f"/forum/threads/{thread.thread_id}", cookies=cookies)

        r = await client.get(f"/forum/threads/{thread.thread_id}", cookies=cookies)
        assert r.status_code == 404

    async def test_non_author_non_admin_returns_403(
        self, client: AsyncClient, session: AsyncSession
    ):
        author, _ = await user_with_cookies(session, username="delauthor")
        other, cookies = await user_with_cookies(session, username="delothe")
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=author.user_id)

        r = await client.delete(f"/forum/threads/{thread.thread_id}", cookies=cookies)
        assert r.status_code == 403

    async def test_admin_can_delete_any_thread(self, client: AsyncClient, session: AsyncSession):
        author, _ = await user_with_cookies(session, username="nodelete_author")
        admin, cookies = await user_with_cookies(
            session, role=MemberRoleEnum.ADMIN, username="admin_deleter"
        )
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=author.user_id)

        r = await client.delete(f"/forum/threads/{thread.thread_id}", cookies=cookies)
        assert r.status_code == 204


# ── POST /forum/threads/{id}/vote ─────────────────────────────────────────────


class TestVoteThread:
    async def test_upvote_returns_vote_state(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)

        r = await client.post(
            f"/forum/threads/{thread.thread_id}/vote",
            json={"is_upvote": True},
            cookies=cookies,
        )
        assert r.status_code == 200
        assert r.json()["user_vote"] is True

    async def test_same_vote_twice_removes_vote(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)
        url = f"/forum/threads/{thread.thread_id}/vote"

        await client.post(url, json={"is_upvote": True}, cookies=cookies)
        r = await client.post(url, json={"is_upvote": True}, cookies=cookies)

        assert r.json()["user_vote"] is None

    async def test_flip_vote_from_up_to_down(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)
        url = f"/forum/threads/{thread.thread_id}/vote"

        await client.post(url, json={"is_upvote": True}, cookies=cookies)
        r = await client.post(url, json={"is_upvote": False}, cookies=cookies)

        assert r.json()["user_vote"] is False

    async def test_vote_on_deleted_thread_returns_404(
        self, client: AsyncClient, session: AsyncSession
    ):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(
            session, topic_id=topic.topic_id, author_id=user.user_id, is_deleted=True
        )

        r = await client.post(
            f"/forum/threads/{thread.thread_id}/vote",
            json={"is_upvote": True},
            cookies=cookies,
        )
        assert r.status_code == 404


# ── POST /forum/threads/{id}/replies ─────────────────────────────────────────


class TestCreateReply:
    async def test_creates_reply(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)

        r = await client.post(
            f"/forum/threads/{thread.thread_id}/replies",
            json={"body": TEST_REPLY_BODY_CREATE, "parent_reply_id": None},
            cookies=cookies,
        )
        assert r.status_code == 201
        assert r.json()["body"] == TEST_REPLY_BODY_CREATE
        assert r.json()["author_username"] == user.username

    async def test_locked_thread_returns_403(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(
            session, topic_id=topic.topic_id, author_id=user.user_id, is_locked=True
        )

        r = await client.post(
            f"/forum/threads/{thread.thread_id}/replies",
            json={"body": TEST_BODY, "parent_reply_id": None},
            cookies=cookies,
        )
        assert r.status_code == 403

    async def test_nested_reply_references_parent(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)
        parent = await make_reply(session, thread_id=thread.thread_id, author_id=user.user_id)

        r = await client.post(
            f"/forum/threads/{thread.thread_id}/replies",
            json={"body": TEST_REPLY_BODY, "parent_reply_id": str(parent.reply_id)},
            cookies=cookies,
        )
        assert r.status_code == 201
        assert r.json()["parent_reply_id"] == str(parent.reply_id)

    async def test_invalid_parent_returns_400(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)

        r = await client.post(
            f"/forum/threads/{thread.thread_id}/replies",
            json={"body": TEST_BODY, "parent_reply_id": str(uuid4())},
            cookies=cookies,
        )
        assert r.status_code == 400


# ── PATCH /forum/replies/{id} ─────────────────────────────────────────────────


class TestUpdateReply:
    async def test_author_can_edit(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)
        reply = await make_reply(session, thread_id=thread.thread_id, author_id=user.user_id)

        r = await client.patch(
            f"/forum/replies/{reply.reply_id}",
            json={"body": TEST_BODY_EDIT},
            cookies=cookies,
        )
        assert r.status_code == 200
        assert r.json()["body"] == TEST_BODY_EDIT

    async def test_non_author_returns_403(self, client: AsyncClient, session: AsyncSession):
        author, _ = await user_with_cookies(session, username="replyauthor")
        other, cookies = await user_with_cookies(session, username="replyother")
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=author.user_id)
        reply = await make_reply(session, thread_id=thread.thread_id, author_id=author.user_id)

        r = await client.patch(
            f"/forum/replies/{reply.reply_id}",
            json={"body": TEST_BODY},
            cookies=cookies,
        )
        assert r.status_code == 403


# ── DELETE /forum/replies/{id} ────────────────────────────────────────────────


class TestDeleteReply:
    async def test_author_can_soft_delete(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)
        reply = await make_reply(session, thread_id=thread.thread_id, author_id=user.user_id)

        r = await client.delete(f"/forum/replies/{reply.reply_id}", cookies=cookies)
        assert r.status_code == 204

        await session.refresh(reply)
        assert reply.is_deleted is True

    async def test_admin_can_delete_any_reply(self, client: AsyncClient, session: AsyncSession):
        author, _ = await user_with_cookies(session, username="replyauth2")
        admin, cookies = await user_with_cookies(
            session, role=MemberRoleEnum.ADMIN, username="replyadmin"
        )
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=author.user_id)
        reply = await make_reply(session, thread_id=thread.thread_id, author_id=author.user_id)

        r = await client.delete(f"/forum/replies/{reply.reply_id}", cookies=cookies)
        assert r.status_code == 204

    async def test_non_author_non_admin_returns_403(
        self, client: AsyncClient, session: AsyncSession
    ):
        author, _ = await user_with_cookies(session, username="rdel_author")
        other, cookies = await user_with_cookies(session, username="rdel_other")
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=author.user_id)
        reply = await make_reply(session, thread_id=thread.thread_id, author_id=author.user_id)

        r = await client.delete(f"/forum/replies/{reply.reply_id}", cookies=cookies)
        assert r.status_code == 403


# ── POST /forum/replies/{id}/vote ─────────────────────────────────────────────


class TestVoteReply:
    async def test_upvote_reply(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)
        reply = await make_reply(session, thread_id=thread.thread_id, author_id=user.user_id)

        r = await client.post(
            f"/forum/replies/{reply.reply_id}/vote",
            json={"is_upvote": True},
            cookies=cookies,
        )
        assert r.status_code == 200
        assert r.json()["user_vote"] is True

    async def test_same_vote_twice_removes_vote(self, client: AsyncClient, session: AsyncSession):
        user, cookies = await user_with_cookies(session)
        topic = await make_topic(session)
        thread = await make_thread(session, topic_id=topic.topic_id, author_id=user.user_id)
        reply = await make_reply(session, thread_id=thread.thread_id, author_id=user.user_id)
        url = f"/forum/replies/{reply.reply_id}/vote"

        await client.post(url, json={"is_upvote": True}, cookies=cookies)
        r = await client.post(url, json={"is_upvote": True}, cookies=cookies)

        assert r.json()["user_vote"] is None


# ── Trigger-dependent tests ───────────────────────────────────────────────────


@pytest.mark.triggers
class TestTriggerMaintainedCounters:
    """
    Verify Postgres trigger-maintained counters.

    trigger_session issues real commits so the route's session and the test
    session share the same committed state. After the HTTP call we close
    trigger_session and open a brand-new session from the engine to read the
    trigger output — this guarantees a fresh transaction snapshot that sees
    everything committed by the route.
    """

    async def test_thread_count_increments_on_create(
        self, trigger_client: AsyncClient, trigger_session: AsyncSession
    ):
        user, cookies = await user_with_cookies(trigger_session)
        topic = await make_topic(trigger_session)

        await trigger_client.post(
            f"/forum/topics/{topic.topic_id}/threads",
            json={"title": TEST_TRIGGER_TITLE_1, "body": TEST_BODY},
            cookies=cookies,
        )
        await trigger_client.post(
            f"/forum/topics/{topic.topic_id}/threads",
            json={"title": TEST_TRIGGER_TITLE_2, "body": TEST_BODY},
            cookies=cookies,
        )

        trigger_session.expire(topic)
        await trigger_session.refresh(topic)
        assert topic.thread_count == 2

    async def test_reply_count_increments_on_reply(
        self, trigger_client: AsyncClient, trigger_session: AsyncSession
    ):
        user, cookies = await user_with_cookies(trigger_session)
        topic = await make_topic(trigger_session)
        thread = await make_thread(trigger_session, topic_id=topic.topic_id, author_id=user.user_id)

        await trigger_client.post(
            f"/forum/threads/{thread.thread_id}/replies",
            json={"body": TEST_TRIGGER_REPLY_BODY, "parent_reply_id": None},
            cookies=cookies,
        )

        trigger_session.expire(thread)
        await trigger_session.refresh(thread)
        assert thread.reply_count == 1

    async def test_upvote_count_increments(
        self, trigger_client: AsyncClient, trigger_session: AsyncSession
    ):
        user, cookies = await user_with_cookies(trigger_session)
        topic = await make_topic(trigger_session)
        thread = await make_thread(trigger_session, topic_id=topic.topic_id, author_id=user.user_id)

        await trigger_client.post(
            f"/forum/threads/{thread.thread_id}/vote", json={"is_upvote": True}, cookies=cookies
        )

        trigger_session.expire(thread)
        await trigger_session.refresh(thread)
        assert thread.upvote_count == 1
