from sqlmodel import create_engine, text, SQLModel
from sqlalchemy.ext.asyncio import AsyncEngine
from src.config import Config
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker


async_engine = AsyncEngine(
    create_engine(
        url=Config.DB_URL,
        echo=True
))

async def init_db():
    '''
        initializes the database if table DNE
        TODO: figure out what metadata is for {conn.run_sync(SQLModel.metadata.create_all)}
    '''
    async with async_engine.begin() as conn:
        from .models import Product

        await conn.run_sync(SQLModel.metadata.create_all)


# dependency injected to route handler
async def get_session() -> AsyncSession:
    Session = sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with Session() as session:
        yield session
