from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from src.auth.auth_routes import auth_router
from src.root_routes import root_router
from src.admin.admin_routes import admin_router
from src.media.media_routes import media_router
from src.config import Config

from contextlib import asynccontextmanager


@asynccontextmanager
async def life_span(app: FastAPI):
    print("Server is starting...")
    # Using Alembic instead to manage DB updates
    yield
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

# app.include_router(router=router, prefix=f"/{api_version}/user")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[Config.ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router=root_router, prefix="")
app.include_router(router=auth_router, prefix="/auth")
app.include_router(router=admin_router, prefix="/admin")
app.include_router(router=media_router, prefix="/media")
# app.include_router(router=product_router, prefix="/products")
# app.include_router(router=member_router, prefix="/member")
