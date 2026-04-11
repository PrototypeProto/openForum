import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from sqlmodel import SQLModel


# Read the -x db_url override BEFORE importing Config.
#
# When the caller passes -x db_url=... they're explicitly telling us which
# database to migrate, and we shouldn't need to instantiate Config (which
# requires POSTGRES_USER/PASSWORD/DB to be present in the environment).
# This lets you run migrations against the test DB from a host shell that
# only has the test container's connection string and no other env vars:
#
#   alembic -x db_url=postgresql+asyncpg://postgres:postgres@localhost:5433/portfolio_test upgrade head
#
# Falls back to Config.DB_URL on the no-override path, which is the normal
# in-container "alembic upgrade head" flow where compose has injected all
# the POSTGRES_* values.
_x_db_url = context.get_x_argument(as_dictionary=True).get("db_url")

if _x_db_url:
    database_url = _x_db_url
else:
    from src.config import Config
    database_url = Config.DB_URL


# Import models so SQLModel.metadata is populated for autogenerate.
# This import chain hits src.db.main which imports Config, so on the
# override path it can still fail if env vars aren't set. That's only
# relevant for `alembic revision --autogenerate`, not plain `upgrade`,
# which alembic runs without consulting target_metadata.
try:
    import src.db.models  # noqa: F401
    target_metadata = SQLModel.metadata
except Exception:
    # If model import fails (e.g. running upgrade with -x db_url against
    # the test DB from a host without env vars set), use empty metadata.
    # Plain upgrade doesn't need target_metadata; only autogenerate does.
    target_metadata = None


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Do NOT use config.set_main_option here — storing a postgresql+asyncpg URL
# there causes Alembic's sync internals to try to load psycopg2.
# The async URL is passed directly to async_engine_from_config instead.

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.
    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # Pass the async URL directly so Alembic never tries to load psycopg2
        url=database_url,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
