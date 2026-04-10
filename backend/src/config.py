import logging
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database ─────────────────────────────────────────────
    DB_URL: str

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
    # If not set explicitly, defaults to DEBUG in development and INFO in production.
    # Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_LEVEL: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
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
