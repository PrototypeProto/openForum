"""
tests/conftest.py
─────────────────
Shared fixtures for the entire test suite.

Infrastructure:
  - Real async Postgres on localhost:5433  (pgsql-test container)
  - Real Redis on localhost:6380           (redis-test container)

Setup (run once, or after any schema/trigger change):
    docker compose --profile test up -d
    alembic -x db_url=postgresql+asyncpg://postgres:postgres@localhost:5433/portfolio_test upgrade head

Running tests:
    pytest                   # 118 standard tests
    pytest --run-triggers    # + 3 trigger tests

Teardown:
    docker compose --profile test down

The engine fixture does NOT call drop_all/create_all — Alembic is the
sole owner of the schema. This means triggers survive across test runs.
Each test uses a SAVEPOINT that is rolled back on teardown for isolation.
Redis is flushed with FLUSHALL after each test.
"""

import os
import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import date
from typing import AsyncGenerator
from dotenv import load_dotenv

# Load .env.test before any src imports so Config picks up the test values
load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env.test"),
    override=True,
)

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# ── App imports (after env is loaded) ────────────────────────────────────────
from src.__init__ import app
from src.db.main import get_session
from src.db.redis_client import _client as redis_client

from src.db.models import User, UserID, PendingUser
from src.db.enums import MemberRoleEnum
from src.auth.utils import (
    create_access_token,
    generate_passwd_hash,
    decode_token,
    REFRESH_TOKEN_EXPIRY_SECONDS,
)
from src.auth.schemas import AccessTokenUserData
from src.db.redis_client import store_refresh_token

# ── Test DB URL ───────────────────────────────────────────────────────────────
TEST_DB_URL = os.environ["TEST_DB_URL"]


# ══════════════════════════════════════════════════════════════════════════════
# Session-scoped: engine + schema
# ══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Connects to the test database managed by Alembic.

    Schema creation and trigger setup are handled entirely by Alembic migrations
    (run once before the test suite with `alembic upgrade head`). This fixture
    only provides the engine — it never touches the schema so triggers and other
    DDL set up by migrations are preserved across test runs.
    """
    _engine = create_async_engine(TEST_DB_URL, echo=False)
    yield _engine
    await _engine.dispose()


# ══════════════════════════════════════════════════════════════════════════════
# Function-scoped: isolated session via SAVEPOINT rollback
# ══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def connection(engine: AsyncEngine) -> AsyncGenerator[AsyncConnection, None]:
    """Raw connection with an outer transaction for per-test rollback isolation."""
    async with engine.connect() as conn:
        await conn.begin()
        yield conn
        await conn.rollback()


@pytest_asyncio.fixture
async def session(connection: AsyncConnection) -> AsyncGenerator[AsyncSession, None]:
    """
    AsyncSession bound to the rolled-back connection.
    Every test gets a clean slate — no data leaks between tests.
    """
    _session = AsyncSession(bind=connection, expire_on_commit=False)
    yield _session
    await _session.close()


# ══════════════════════════════════════════════════════════════════════════════
# Redis flush — runs after every test
# ══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture(autouse=True)
async def flush_redis():
    """
    Flush all Redis keys after each test so key state never leaks.
    Uses the real redis-test container — consistent with production behaviour.
    """
    yield
    await redis_client.flushall()


# ══════════════════════════════════════════════════════════════════════════════
# HTTP client with dependency overrides
# ══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient wired to the app with the test DB session injected.
    Use this for HTTP-level integration tests.
    """

    async def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════════
# Test data factories
# ══════════════════════════════════════════════════════════════════════════════


async def make_user(
    session: AsyncSession,
    *,
    username: str = None,
    role: MemberRoleEnum = MemberRoleEnum.USER,
    password: str = "testpassword",
) -> User:
    """
    Insert a verified User directly into the DB, bypassing the pending flow.
    Returns the User ORM object.
    """
    username = username or f"user_{uuid4().hex[:8]}"

    user_id_row = UserID()
    session.add(user_id_row)
    await session.commit()
    await session.refresh(user_id_row)

    user = User(
        user_id=user_id_row.id,
        username=username,
        password_hash=generate_passwd_hash(password),
        join_date=date.today(),
        verified_date=date.today(),
        last_login_date=None,
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def make_access_token(user: User) -> str:
    """Issue a valid access token for `user` without hitting the DB."""
    data = AccessTokenUserData(
        user_id=str(user.user_id),
        username=user.username,
        nickname=user.nickname,
    ).model_dump()
    return create_access_token(user_data=data)


async def make_refresh_token(user: User) -> str:
    """Issue a refresh token and register its JTI in Redis."""
    data = AccessTokenUserData(
        user_id=str(user.user_id),
        username=user.username,
        nickname=user.nickname,
    ).model_dump()
    token = create_access_token(
        user_data=data,
        expiry_seconds=REFRESH_TOKEN_EXPIRY_SECONDS,
        refresh=True,
    )
    token_data = decode_token(token)
    await store_refresh_token(
        jti=token_data["jti"],
        username=user.username,
        ttl_seconds=REFRESH_TOKEN_EXPIRY_SECONDS,
    )
    return token


def auth_cookies(access_token: str, refresh_token: str = "") -> dict:
    """Return a cookies dict suitable for httpx requests."""
    cookies = {"access_token": access_token}
    if refresh_token:
        cookies["refresh_token"] = refresh_token
    return cookies


# ══════════════════════════════════════════════════════════════════════════════
# Trigger test fixtures
# ══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def trigger_session() -> AsyncGenerator[AsyncSession, None]:
    """
    A session backed by its own dedicated engine — required for trigger tests.

    Uses a separate engine (not the shared test engine) so it gets its own
    connection pool with no shared transaction state. Each commit() is a real
    COMMIT to Postgres, making trigger output visible on the next refresh().

    expire_on_commit=False is kept to prevent MissingGreenlet errors when
    accessing attributes after commit outside of an await context.
    We call session.expire(obj) explicitly before refresh() to force a re-read.
    """
    _engine = create_async_engine(TEST_DB_URL, echo=False, pool_size=2)
    _session = AsyncSession(_engine, expire_on_commit=False)
    yield _session
    await _session.close()
    await _engine.dispose()


@pytest_asyncio.fixture
async def trigger_client(
    trigger_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient wired to trigger_session (real commits) instead of the
    savepoint session. Use alongside trigger_session in trigger tests.
    """

    async def _override():
        yield trigger_session

    app.dependency_overrides[get_session] = _override

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════════
# pytest CLI option for trigger-dependent tests
# ══════════════════════════════════════════════════════════════════════════════


def pytest_addoption(parser):
    parser.addoption(
        "--run-triggers",
        action="store_true",
        default=False,
        help="Run tests that depend on Postgres triggers (requires alembic upgrade head on the test DB)",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-triggers"):
        skip_triggers = pytest.mark.skip(
            reason="Requires Postgres triggers — run with --run-triggers after applying migrations"
        )
        for item in items:
            if "triggers" in item.keywords:
                item.add_marker(skip_triggers)
