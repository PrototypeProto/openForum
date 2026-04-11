import logging
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database components ───────────────────────────────────
    # POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB come from
    # the root .env (the same file compose.yaml reads for the
    # pgsql-db service environment), so dev creds live in one
    # place. POSTGRES_HOST / POSTGRES_PORT come from backend/.env
    # because they describe the CONTAINER-side address the
    # backend connects to over the docker network — unrelated
    # to the host-side port mapping in compose.yaml.
    #
    # Inside docker: compose's `env_file: [./.env, ./backend/.env]`
    # injects all of these into the server-py container env.
    # Outside docker (e.g. pytest): tests/conftest.py loads
    # backend/.env.test which sets all five POSTGRES_* values
    # explicitly so they override anything from backend/.env.
    POSTGRES_HOST: str = "pgsql-db"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # ── Redis ─────────────────────────────────────────────────
    REDIS_HOST: str = "redis-db"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # ── JWT ───────────────────────────────────────────────────
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    # ── CORS ──────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    # ── Storage paths ─────────────────────────────────────────
    MEDIA_DIR: str = "shared_media"
    TEMPFS_DIR: str = "tempfs_storage"
    LOGS_DIR: str = "logs"

    # ── Environment ───────────────────────────────────────────
    # development | production
    # Drives: cookie secure flag, SQLAlchemy echo, log level
    ENVIRONMENT: str = "development"

    # ── Logging ───────────────────────────────────────────────
    # If not set explicitly, defaults to DEBUG in development
    # and INFO in production.
    # Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_LEVEL: str = ""

    model_config = SettingsConfigDict(
        # In Docker: compose injects env vars from ../.env and ./backend/.env
        # directly into the container, so pydantic picks them up via
        # os.environ without touching the filesystem.
        #
        # Outside Docker (local dev, pytest): pydantic reads backend/.env
        # relative to CWD. For pytest, conftest.py calls load_dotenv on
        # backend/.env.test BEFORE this Settings instance is constructed,
        # populating os.environ with test values that take precedence.
        #
        # extra="ignore" matters because compose injects keys this class
        # doesn't know about (POSTGRES_HOST_PORT for port mapping, etc.).
        # Without it pydantic would crash at startup.
        env_file=".env",
        extra="ignore",
    )

    # ── Computed fields ───────────────────────────────────────

    @computed_field
    @property
    def DB_URL(self) -> str:
        """Assembled asyncpg connection string, built from POSTGRES_* parts."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cookie_secure(self) -> bool:
        """True in production (requires HTTPS), False in development."""
        return self.is_production

    @property
    def log_level(self) -> int:
        """Resolved log level as a logging int constant."""
        if self.LOG_LEVEL:
            return getattr(logging, self.LOG_LEVEL.upper(), logging.INFO)
        return logging.INFO if self.is_production else logging.DEBUG

    @property
    def db_echo(self) -> bool:
        """SQLAlchemy query logging — only in development."""
        return not self.is_production


Config = Settings()
