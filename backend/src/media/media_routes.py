import contextlib
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import aiofiles
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.dependencies import require_admin, require_user
from src.config import Config
from src.db.main import get_session
from src.db.schemas import PaginatedMedia
from src.exceptions import (
    BadRequestError,
    FileNotFoundError,
    FileTooLargeError,
    InvalidPathError,
    UnsupportedFileTypeError,
)

from .service import MediaService

router = APIRouter(prefix="/media", tags=["media"])
media_service = MediaService()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]

MEDIA_DIR = Path(Config.MEDIA_DIR)
MEDIA_LIMIT = 2
MEDIA_MAX_SIZE = 100 * 1024 * 1024  # 100 MB hard cap on media uploads
MEDIA_CHUNK = 1024 * 1024  # 1 MB streaming chunk

MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
ALLOWED_EXTENSIONS = set(MEDIA_TYPES.keys())
ALLOWED_MIME_TYPES = set(MEDIA_TYPES.values())


def _sniff_extension(head: bytes) -> str | None:
    """
    Identify file type from its leading bytes. Returns the canonical
    extension (with dot) or None if the bytes don't match the allowlist.
    Never trust the client-supplied Content-Type or filename for this.
    """
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    # ISO-BMFF (mp4): bytes 4..8 are the major box type "ftyp"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return ".mp4"
    return None


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
    """
    Admin-only media upload.

    Hardening notes:
      - Original filename is NEVER joined onto the filesystem path. We
        generate the stored name as `{uuid4}{sniffed_ext}`. This makes
        path traversal structurally impossible.
      - The client-sent Content-Type is ignored. We sniff the actual
        leading bytes against an allowlist (jpg/png/mp4).
      - Body is streamed in chunks; we abort the moment the running
        size exceeds MEDIA_MAX_SIZE so a malicious client can't OOM us.
      - On any failure mid-stream the partial file is removed.
    """
    # Read enough bytes to sniff the type. The first 1 MB chunk also
    # becomes the first thing we write to disk so we don't double-buffer.
    first_chunk = await file.read(MEDIA_CHUNK)
    if not first_chunk:
        raise BadRequestError("Empty file")

    ext = _sniff_extension(first_chunk[:16])
    if ext is None or ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError("Unsupported or unrecognized file type")

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{ext}"
    file_path = (MEDIA_DIR / stored_name).resolve()

    # Belt-and-suspenders: a UUID hex can't escape the dir, but check anyway.
    if not file_path.is_relative_to(MEDIA_DIR.resolve()):
        raise InvalidPathError("Invalid file path")

    total = 0
    try:
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(first_chunk)
            total += len(first_chunk)
            if total > MEDIA_MAX_SIZE:
                raise FileTooLargeError("File exceeds media upload limit")

            while chunk := await file.read(MEDIA_CHUNK):
                total += len(chunk)
                if total > MEDIA_MAX_SIZE:
                    raise FileTooLargeError("File exceeds media upload limit")
                await f.write(chunk)
    except Exception:
        # Clean up the partial file on any failure
        with contextlib.suppress(OSError):
            file_path.unlink(missing_ok=True)
        raise

    return {"filename": stored_name}


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
