from typing import Optional, Union, Annotated, List
from fastapi import FastAPI, Header, APIRouter, Depends, UploadFile, File, Query, Cookie
from fastapi import status
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.exceptions import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from src.auth.service import AuthService
from src.db.main import get_session
from datetime import datetime, timedelta
from src.auth.dependencies import (
    RefreshTokenBearer,
    access_token_bearer,
    get_current_user_uuid,
    get_current_user_by_username,
)
from .service import MediaService
from uuid import UUID
from src.config import Config
from pathlib import Path
from src.admin.service import AdminService
import aiofiles
from pydantic import Field

REFRESH_TOKEN_EXPIRY_DAYS = 2

media_router = APIRouter(dependencies=[access_token_bearer])

auth_service = AuthService()
media_service = MediaService()
admin_service = AdminService()

SessionDependency = Annotated[AsyncSession, Depends(get_session)]

MEDIA_LIMIT = 2
MEDIA_DIR = Path(Config.MEDIA_DIR)

ALLOWED_EXTENSIONS = {".mp4", ".jpg", ".jpeg", ".png"}
MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
ALLOWED_MIME_TYPES = set(MEDIA_TYPES.values())
ALLOWED_EXTENSIONS = set(MEDIA_TYPES.keys())

@media_router.get("/pages", response_model=int)
async def get_page_count(
    session: SessionDependency,
    token_details: dict = access_token_bearer):
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid perms"
        )
    
    return 2

@media_router.get("/list")
async def list_media_page(
    session: SessionDependency,
    page: int = Query(default=1, ge=1),
    token_details: dict = access_token_bearer,
):
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid perms"
        )
    return await media_service.list_accessible_media(page-1, MEDIA_LIMIT)


@media_router.get("/{filename}")
async def get_media(
    filename: str, session: SessionDependency, token_details: dict = access_token_bearer
):
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid perms"
        )

    # resolve into real path
    file_path = (MEDIA_DIR / filename).resolve()

    # if resolved path escapes MEDIA_DIR, reject it
    if not file_path.is_relative_to(MEDIA_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    media_type = MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(path=file_path, media_type=media_type, filename=file_path.name)


# FOR ADMINS
# FOR ADMINS
# FOR ADMINS


@media_router.post("/file", status_code=status.HTTP_201_CREATED)
async def upload_file(
    session: SessionDependency,
    file: UploadFile = File(...),
    token_details: dict = access_token_bearer,
):
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions"
        )
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type"
        )

    file_path: Path = MEDIA_DIR / file.filename
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # read in 1MB chunks
            await f.write(chunk)

    return {"filename": file.filename}

@media_router.delete("/file/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(session: SessionDependency, filename: str, token_details: dict = access_token_bearer):
    if not await admin_service.verify_admin(token_details, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions"
        )
    # resolve into real path
    file_path = (MEDIA_DIR / filename).resolve()

    # if resolved path escapes MEDIA_DIR, reject it
    if not str(file_path).startswith(str(MEDIA_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    try:
        file_path.unlink()
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="failed to locate file")