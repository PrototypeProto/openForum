"""
tests/test_sanitisation.py
──────────────────────────
Tests for two related security fixes:

Fix 6 — delete_cookie attribute matching
  Verifies that logout and refresh-reuse responses include Set-Cookie headers
  that properly expire the auth cookies with the same path/secure/samesite
  attributes used at set time. Without matching attributes, some browsers
  (notably Safari) silently ignore the deletion.

Fix 8 — Forum body XSS sanitisation
  Verifies that _sanitise_body() in forum/service.py strips disallowed HTML
  from thread and reply bodies before storage.

  Pure unit tests for _sanitise_body() cover:
    - Safe tags preserved
    - Script tags stripped (text content kept)
    - Event handler attributes stripped
    - javascript: href sanitised
    - Nested XSS payloads
    - Empty / None input

  Integration tests via the service layer (forum_svc + session) verify
  that create_thread, update_thread, create_reply, and update_reply all
  call _sanitise_body before persisting.
"""

from uuid import uuid4

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.models import Topic, TopicGroup
from src.db.schemas import ReplyCreate, ReplyUpdate, ThreadCreate, ThreadUpdate
from src.forum.service import _sanitise_body
from tests.conftest import auth_cookies, make_access_token, make_user
from tests.constants import TEST_BODY, TEST_TITLE

# ══════════════════════════════════════════════════════════════════════════════
# Fix 6 — delete_cookie attribute matching
# ══════════════════════════════════════════════════════════════════════════════


class TestDeleteCookieAttributes:
    """
    Starlette's delete_cookie() is implemented by setting the cookie value
    to "" with Max-Age=0. For the deletion to take effect in all browsers,
    the path/secure/samesite attributes must match the original set_cookie call.

    We check the raw Set-Cookie headers rather than r.cookies because
    httpx's cookie jar doesn't expose expired cookies.
    """

    def _parse_set_cookie_headers(self, response, cookie_name: str) -> list[str]:
        """Return all Set-Cookie header values that mention cookie_name."""
        return [
            v.lower()
            for k, v in response.headers.multi_items()
            if k == "set-cookie" and cookie_name.lower() in v.lower()
        ]

    async def test_logout_access_token_deletion_has_path(
        self, client: AsyncClient, session: AsyncSession
    ):
        user = await make_user(session, username="delpath_access")
        token = make_access_token(user)

        r = await client.post("/auth/logout", cookies=auth_cookies(token))

        headers = self._parse_set_cookie_headers(r, "access_token")
        assert headers, "access_token Set-Cookie header missing"
        assert "path=/" in headers[0], f"path=/ not in: {headers[0]}"

    async def test_logout_refresh_token_deletion_has_path(
        self, client: AsyncClient, session: AsyncSession
    ):
        user = await make_user(session, username="delpath_refresh")
        token = make_access_token(user)

        r = await client.post("/auth/logout", cookies=auth_cookies(token))

        headers = self._parse_set_cookie_headers(r, "refresh_token")
        assert headers, "refresh_token Set-Cookie header missing"
        assert "path=/" in headers[0]

    async def test_logout_cookies_have_max_age_zero(
        self, client: AsyncClient, session: AsyncSession
    ):
        user = await make_user(session, username="maxage_check")
        token = make_access_token(user)

        r = await client.post("/auth/logout", cookies=auth_cookies(token))

        all_set_cookie = " ".join(v for k, v in r.headers.multi_items() if k == "set-cookie")
        # Max-Age=0 signals deletion
        assert "max-age=0" in all_set_cookie.lower()

    async def test_login_clear_cookies_have_path(self, client: AsyncClient, session: AsyncSession):
        """
        Login pre-clears any existing cookies before issuing new ones.
        These pre-clear deletions must also carry path=/ so they take effect.
        """
        await make_user(session, username="loginclear")

        r = await client.post(
            "/auth/login",
            json={"username": "loginclear", "password": "testpassword1"},
        )
        assert r.status_code == 200

        # All Set-Cookie headers with Max-Age=0 should have path=/
        expired_headers = [
            v.lower()
            for k, v in r.headers.multi_items()
            if k == "set-cookie" and "max-age=0" in v.lower()
        ]
        for h in expired_headers:
            assert "path=/" in h, f"path=/ missing from deletion header: {h}"

    async def test_csrf_cookie_deletion_has_path(self, client: AsyncClient, session: AsyncSession):
        user = await make_user(session, username="csrfpath_del")
        token = make_access_token(user)

        r = await client.post("/auth/logout", cookies=auth_cookies(token))

        # csrf_token deletion must also carry path=/
        csrf_headers = [
            v.lower()
            for k, v in r.headers.multi_items()
            if k == "set-cookie" and "csrf_token" in v.lower() and "max-age=0" in v.lower()
        ]
        assert csrf_headers, "No expired csrf_token Set-Cookie found"
        assert "path=/" in csrf_headers[0]


# ══════════════════════════════════════════════════════════════════════════════
# Fix 8 — _sanitise_body pure unit tests (no DB, no fixtures)
# ══════════════════════════════════════════════════════════════════════════════


class TestSanitiseBodyPure:
    # ── Safe content preserved ────────────────────────────────────────────────

    def test_plain_text_unchanged(self):
        assert _sanitise_body("Hello world") == "Hello world"

    def test_allowed_bold_preserved(self):
        result = _sanitise_body("<b>bold</b>")
        assert "<b>bold</b>" in result

    def test_allowed_italic_preserved(self):
        result = _sanitise_body("<em>italic</em>")
        assert "<em>italic</em>" in result

    def test_allowed_code_preserved(self):
        result = _sanitise_body("<code>x = 1</code>")
        assert "<code>x = 1</code>" in result

    def test_allowed_link_preserved(self):
        result = _sanitise_body('<a href="https://example.com">link</a>')
        assert "https://example.com" in result
        assert "link" in result

    def test_allowed_list_preserved(self):
        result = _sanitise_body("<ul><li>item</li></ul>")
        assert "item" in result

    # ── Disallowed tags stripped, text content kept ───────────────────────────

    def test_script_tag_stripped(self):
        result = _sanitise_body("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "</script>" not in result

    def test_script_text_content_kept(self):
        """Text inside script should survive (it's just text, not executable)."""
        result = _sanitise_body("<script>alert('xss')</script>harmless")
        assert "harmless" in result

    def test_style_tag_stripped(self):
        result = _sanitise_body("<style>body{display:none}</style>text")
        assert "<style>" not in result
        assert "text" in result

    def test_img_tag_stripped(self):
        result = _sanitise_body('<img src="x" onerror="alert(1)">text')
        assert "<img" not in result
        assert "text" in result

    def test_iframe_stripped(self):
        result = _sanitise_body('<iframe src="evil.com"></iframe>')
        assert "<iframe" not in result

    def test_object_stripped(self):
        result = _sanitise_body("<object data='x'></object>text")
        assert "<object" not in result
        assert "text" in result

    # ── Dangerous attributes stripped ─────────────────────────────────────────

    def test_onerror_attribute_stripped(self):
        result = _sanitise_body('<b onerror="alert(1)">text</b>')
        assert "onerror" not in result
        assert "text" in result

    def test_onclick_attribute_stripped(self):
        result = _sanitise_body('<b onclick="evil()">text</b>')
        assert "onclick" not in result

    def test_onmouseover_stripped(self):
        result = _sanitise_body('<em onmouseover="steal()">text</em>')
        assert "onmouseover" not in result

    def test_javascript_href_sanitised(self):
        result = _sanitise_body('<a href="javascript:alert(1)">click</a>')
        assert "javascript:" not in result

    def test_data_uri_href_sanitised(self):
        result = _sanitise_body('<a href="data:text/html,<script>alert(1)</script>">x</a>')
        assert "data:" not in result or "<script>" not in result

    def test_style_attribute_stripped(self):
        result = _sanitise_body('<b style="color:red;background:url(x)">text</b>')
        assert "style=" not in result

    # ── Nested / obfuscated payloads ──────────────────────────────────────────

    def test_nested_script_stripped(self):
        result = _sanitise_body("<div><script>alert(1)</script></div>")
        assert "<script>" not in result

    def test_mixed_safe_and_unsafe(self):
        raw = "<b>bold</b> <script>evil()</script> <em>italic</em>"
        result = _sanitise_body(raw)
        assert "<b>bold</b>" in result
        assert "<script>" not in result
        assert "<em>italic</em>" in result

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_none_returns_empty_string(self):
        assert _sanitise_body(None) == ""

    def test_empty_string_returns_empty(self):
        assert _sanitise_body("") == ""

    def test_plain_text_with_no_html_unchanged(self):
        msg = "Just a regular comment with no HTML at all."
        assert _sanitise_body(msg) == msg


# ══════════════════════════════════════════════════════════════════════════════
# Fix 8 — sanitisation wired into service write paths
# ══════════════════════════════════════════════════════════════════════════════


async def _make_group(session: AsyncSession) -> TopicGroup:
    g = TopicGroup(name=f"g_{uuid4().hex[:6]}", display_order=0)
    session.add(g)
    await session.commit()
    await session.refresh(g)
    return g


async def _make_topic(session: AsyncSession) -> Topic:
    g = await _make_group(session)
    t = Topic(
        group_id=g.group_id,
        name=f"t_{uuid4().hex[:6]}",
        display_order=0,
        thread_count=0,
        reply_count=0,
    )
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


class TestSanitisationWired:
    async def test_create_thread_strips_script(self, forum_svc, session: AsyncSession):
        user = await make_user(session, username="xss_thread_create")
        topic = await _make_topic(session)

        payload = ThreadCreate(
            title=TEST_TITLE,
            body="Safe text <script>alert('xss')</script>",
        )
        result = await forum_svc.create_thread(topic.topic_id, user.user_id, payload, session)

        assert "<script>" not in result.body
        assert "Safe text" in result.body

    async def test_update_thread_strips_script(self, forum_svc, session: AsyncSession):
        from src.db.models import Thread

        user = await make_user(session, username="xss_thread_update")
        topic = await _make_topic(session)

        thread = Thread(
            topic_id=topic.topic_id,
            author_id=user.user_id,
            title=TEST_TITLE,
            body=TEST_BODY,
        )
        session.add(thread)
        await session.commit()
        await session.refresh(thread)

        payload = ThreadUpdate(body="Updated <script>steal()</script> text")
        result = await forum_svc.update_thread(thread, user.user_id, payload, session)

        assert "<script>" not in result.body
        assert "Updated" in result.body
        assert "text" in result.body

    async def test_create_reply_strips_script(self, forum_svc, session: AsyncSession):
        from src.db.models import Thread

        user = await make_user(session, username="xss_reply_create")
        topic = await _make_topic(session)

        thread = Thread(
            topic_id=topic.topic_id,
            author_id=user.user_id,
            title=TEST_TITLE,
            body=TEST_BODY,
        )
        session.add(thread)
        await session.commit()
        await session.refresh(thread)

        payload = ReplyCreate(
            body='Hello <img src="x" onerror="alert(1)"> world',
            parent_reply_id=None,
        )
        result = await forum_svc.create_reply(thread.thread_id, user.user_id, payload, session)

        assert "onerror" not in result.body
        assert "Hello" in result.body
        assert "world" in result.body

    async def test_update_reply_strips_script(self, forum_svc, session: AsyncSession):
        from src.db.models import Reply, Thread

        user = await make_user(session, username="xss_reply_update")
        topic = await _make_topic(session)

        thread = Thread(
            topic_id=topic.topic_id,
            author_id=user.user_id,
            title=TEST_TITLE,
            body=TEST_BODY,
        )
        session.add(thread)
        await session.commit()
        await session.refresh(thread)

        reply = Reply(
            thread_id=thread.thread_id,
            author_id=user.user_id,
            body=TEST_BODY,
        )
        session.add(reply)
        await session.commit()
        await session.refresh(reply)

        payload = ReplyUpdate(body="<script>evil()</script>clean text")
        result = await forum_svc.update_reply(reply, payload, session)

        assert "<script>" not in result.body
        assert "clean text" in result.body

    async def test_safe_formatting_survives_create(self, forum_svc, session: AsyncSession):
        """Allowed tags must not be stripped — only malicious content."""
        user = await make_user(session, username="safe_fmt_create")
        topic = await _make_topic(session)

        payload = ThreadCreate(
            title=TEST_TITLE,
            body="<b>bold</b> and <em>italic</em> and <code>code</code>",
        )
        result = await forum_svc.create_thread(topic.topic_id, user.user_id, payload, session)

        assert "<b>bold</b>" in result.body
        assert "<em>italic</em>" in result.body
        assert "<code>code</code>" in result.body

    async def test_plain_text_body_unchanged_on_create(self, forum_svc, session: AsyncSession):
        user = await make_user(session, username="plain_txt_create")
        topic = await _make_topic(session)

        payload = ThreadCreate(title=TEST_TITLE, body=TEST_BODY)
        result = await forum_svc.create_thread(topic.topic_id, user.user_id, payload, session)

        assert result.body == TEST_BODY
