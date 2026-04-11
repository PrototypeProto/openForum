import logging

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valid ENVIRONMENT values — validated at startup so a typo fails loudly
# instead of silently behaving like development.
_VALID_ENVIRONMENTS = {"development", "testing", "production", "staging"}


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
    # Outside docker (e.g. pytest): tests/conftest.py calls load_dotenv on
    # backend/.env.test BEFORE this Settings instance is constructed,
    # populating os.environ with test values that take precedence.
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
    # Comma-separated list of allowed origins. Multiple values supported:
    #   ALLOWED_ORIGINS=https://example.com,https://www.example.com
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    # Enumerate the methods and headers the frontend actually uses.
    # Restricting these reduces preflight attack surface vs allow_methods=["*"].
    CORS_ALLOW_METHODS: str = "GET,POST,PATCH,DELETE,OPTIONS"
    CORS_ALLOW_HEADERS: str = "Content-Type,X-CSRF-Token,X-File-Password"

    # ── Storage paths ─────────────────────────────────────────
    MEDIA_DIR: str = "shared_media"
    TEMPFS_DIR: str = "tempfs_storage"
    LOGS_DIR: str = "logs"

    # ── Environment ───────────────────────────────────────────
    # Valid values: development | testing | staging | production
    #
    #   development  — local dev server; echo on, cookies insecure, debug logs
    #   testing      — pytest suite; echo off, scheduler off, rate limits off
    #   staging      — pre-prod deploy; behaves like production in security
    #                  posture (secure cookies, no echo) but points at staging
    #                  infra via its own .env / CI env vars
    #   production   — live; all hardening on
    ENVIRONMENT: str = "development"

    # ── Rate limiting ─────────────────────────────────────────
    # Set to true in .env.test so the test suite never hits 429s
    # from repeated calls to the same endpoint within one test.
    # Never set true in staging or production.
    DISABLE_RATE_LIMIT: bool = False

    # ── Logging ───────────────────────────────────────────────
    # If not set explicitly, defaults to DEBUG in development,
    # WARNING in testing (keeps pytest output clean), INFO elsewhere.
    # Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_LEVEL: str = ""

    @field_validator("ENVIRONMENT")
    @classmethod
    def _validate_environment(cls, v: str) -> str:
        if v not in _VALID_ENVIRONMENTS:
            raise ValueError(f"ENVIRONMENT must be one of {sorted(_VALID_ENVIRONMENTS)}, got {v!r}")
        return v

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

    # ── Environment predicates ────────────────────────────────

    @property
    def is_testing(self) -> bool:
        """True only when running the pytest suite."""
        return self.ENVIRONMENT == "testing"

    @property
    def is_production(self) -> bool:
        """True for production and staging — both require full security posture."""
        return self.ENVIRONMENT in ("production", "staging")

    @property
    def is_development(self) -> bool:
        """True only for the local dev server."""
        return self.ENVIRONMENT == "development"

    # ── Derived settings ──────────────────────────────────────

    @property
    def cookie_secure(self) -> bool:
        """Require HTTPS for cookies in production/staging; off elsewhere."""
        return self.is_production

    @property
    def cookie_samesite(self) -> str:
        """
        SameSite policy for auth cookies.

        "strict" in production/staging — once frontend and backend share an
        origin behind nginx, cross-site requests carrying cookies are fully
        blocked. "lax" in development/testing so the httpx test client and
        local Vite dev server can still send cookies.
        """
        return "strict" if self.is_production else "lax"

    @property
    def allowed_origins_list(self) -> list[str]:
        """ALLOWED_ORIGINS parsed from comma-separated string into a list."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def cors_allow_methods_list(self) -> list[str]:
        """CORS_ALLOW_METHODS parsed from comma-separated string into a list."""
        return [m.strip() for m in self.CORS_ALLOW_METHODS.split(",") if m.strip()]

    @property
    def cors_allow_headers_list(self) -> list[str]:
        """CORS_ALLOW_HEADERS parsed from comma-separated string into a list."""
        return [h.strip() for h in self.CORS_ALLOW_HEADERS.split(",") if h.strip()]

    @property
    def log_level(self) -> int:
        """
        Resolved log level as a logging int constant.

        Priority:
          1. Explicit LOG_LEVEL env var (any environment)
          2. WARNING  in testing  — keeps pytest output clean
          3. INFO     in production/staging
          4. DEBUG    in development
        """
        if self.LOG_LEVEL:
            return getattr(logging, self.LOG_LEVEL.upper(), logging.INFO)
        if self.is_testing:
            return logging.WARNING
        return logging.INFO if self.is_production else logging.DEBUG

    @property
    def db_echo(self) -> bool:
        """
        SQLAlchemy query logging.
        On only in development — off in testing (reduces noise) and production.
        """
        return self.is_development


Config = Settings()
