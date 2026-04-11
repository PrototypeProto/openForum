from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from src.config import Config
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager


async_engine: AsyncEngine = create_async_engine(Config.DB_URL, echo=Config.db_echo)

_SessionFactory = sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)


# dependency injected to route handler
async def get_session() -> AsyncSession:
    async with _SessionFactory() as session:
        yield session


# context manager for use outside of FastAPI dependency injection (e.g. scheduler)
@asynccontextmanager
async def get_session_context() -> AsyncSession:
    async with _SessionFactory() as session:
        yield session
