from typing import Optional, Union, Annotated
'''
    Optional[type(s)]
    Union() or (type | None)
    Annotated[type, "annotation textr"]
'''
from fastapi import FastAPI, Header
from src.auth.auth_routes import auth_router
from src.root_routes import root_router
from src.config import Settings
from src.db.main import init_db

from contextlib import asynccontextmanager

@asynccontextmanager
async def life_span(app: FastAPI):
    print("Server is starting...")
    
    # If we want to autogenerate the DB based on our SQLModels
    # Using Alembic instead to manage DB updates
    # await init_db()
    
    yield
    print("Server has been stopped...")

# api_version = "v1"
# s = Settings()
# print(s.DB_URL)

# app = FastAPI(version=api_version)
app = FastAPI(
    title="Portfolio",
    description="My portfolio & community for friends",
    lifespan=life_span
)

# app.include_router(router=router, prefix=f"/{api_version}/user")
app.include_router(router=auth_router, prefix="/auth")
app.include_router(router=root_router, prefix="")
# app.include_router(router=product_router, prefix="/products")
# app.include_router(router=member_router, prefix="/member")
