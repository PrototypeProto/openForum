from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from src.exceptions import AppException
from fastapi.middleware.cors import CORSMiddleware
from src.auth.middleware import TokenRefreshMiddleware
from src.root_routes import router as root_router
from src.auth.auth_routes import router as auth_router
from src.admin.admin_routes import router as admin_router
from src.media.media_routes import router as media_router
from src.forum.forum_routes import router as forum_router 
from src.tempfs.tempfs_routes import router as tempfs_router
from src.tempfs.scheduler import start_scheduler, stop_scheduler
from src.config import Config
from contextlib import asynccontextmanager


@asynccontextmanager
async def life_span(app: FastAPI):
    print("Server is starting...")
    start_scheduler()
    yield
    stop_scheduler()
    print("Server has been stopped...")


# api_version = "v1"
# s = Settings()
# print(s.DB_URL)

# app = FastAPI(version=api_version)
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

# app.include_router(router=router, prefix=f"/{api_version}/user")
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