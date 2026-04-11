"""
src/app.py
──────────
FastAPI application construction.

Lives in app.py (not __init__.py) so that `from src.config import Config`
and other narrow imports don't trigger loading the entire FastAPI app, its
middleware, all routers, and the scheduler. Keeping the package's
__init__.py empty means lightweight scripts (alembic migrations, one-off
CLI tools, tests that only need a single helper) can import from `src.*`
without booting the whole stack.

Uvicorn entry point: `uvicorn src.app:app`
Tests: `from src.app import app`
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.admin.admin_routes import router as admin_router
from src.auth.auth_routes import router as auth_router
from src.auth.middleware import TokenRefreshMiddleware
from src.config import Config
from src.exceptions import AppException
from src.forum.forum_routes import router as forum_router
from src.media.media_routes import router as media_router
from src.root_routes import router as root_router
from src.tempfs.scheduler import start_scheduler, stop_scheduler
from src.tempfs.tempfs_routes import router as tempfs_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def life_span(app: FastAPI):
    logger.info("Server is starting...")
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("Server has been stopped.")


app = FastAPI(
    title="Portfolio",
    description="My portfolio & community for friends",
    lifespan=life_span,
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "detail": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for anything that isn't an AppException.

    Prevents raw tracebacks from leaking to the client while still
    logging the full error server-side so we can debug. Covers Redis
    ConnectionError, unexpected DB errors, and anything else we missed.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": "An unexpected error occurred"},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[Config.ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TokenRefreshMiddleware)
app.include_router(router=root_router)
app.include_router(router=auth_router)
app.include_router(router=admin_router)
app.include_router(router=media_router)
app.include_router(router=forum_router)
app.include_router(router=tempfs_router)
