from typing import Annotated
from fastapi import APIRouter, Depends, UploadFile, File, Query, status
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.main import get_session
from src.auth.dependencies import require_user, require_admin
from .service import MediaService
from src.config import Config
from pathlib import Path
from src.db.schemas import PaginatedMedia
from src.exceptions import (
    InvalidPathError,
    FileNotFoundError,
    UnsupportedFileTypeError,
    BadRequestError,
)
import aiofiles

router = APIRouter(prefix="/media", tags=["media"])
media_service = MediaService()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]

MEDIA_DIR = Path(Config.MEDIA_DIR)
MEDIA_LIMIT = 2

MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
ALLOWED_EXTENSIONS = set(MEDIA_TYPES.keys())
ALLOWED_MIME_TYPES = set(MEDIA_TYPES.values())


@router.get("/list", response_model=PaginatedMedia)
async def list_media_page(
    session: SessionDependency,
    page: int = Query(default=1, ge=1),
    token_details: dict = require_user,
):
    return await media_service.list_accessible_media(page, MEDIA_LIMIT)


@router.get("/{filename}")
async def get_media(
    filename: str,
    session: SessionDependency,
    token_details: dict = require_user,
):
    file_path = (MEDIA_DIR / filename).resolve()

    if not file_path.is_relative_to(MEDIA_DIR.resolve()):
        raise InvalidPathError("Invalid file path")
    if not file_path.exists():
        raise FileNotFoundError("File not found")
    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError("Unsupported file type")

    media_type = MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(path=file_path, media_type=media_type, filename=file_path.name)


@router.post("/file", status_code=status.HTTP_201_CREATED)
async def upload_file(
    session: SessionDependency,
    file: UploadFile = File(...),
    token_details: dict = require_admin,
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise UnsupportedFileTypeError("Unsupported file type")

    file_path: Path = MEDIA_DIR / file.filename
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            await f.write(chunk)

    return {"filename": file.filename}


@router.delete("/file/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    filename: str,
    session: SessionDependency,
    token_details: dict = require_admin,
):
    file_path = (MEDIA_DIR / filename).resolve()

    if not file_path.is_relative_to(MEDIA_DIR.resolve()):
        raise InvalidPathError("Invalid file path")
    if not file_path.exists():
        raise FileNotFoundError("File not found")
    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError("Unsupported file type")

    try:
        file_path.unlink()
    except OSError as exc:
        raise BadRequestError("Failed to delete file") from exc
