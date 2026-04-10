"""
/tempfs routes
VIP and Admin only for upload/list/storage. Download access depends on file permission setting.
"""
import io
from typing import Annotated, Optional
from uuid import UUID

import zstandard as zstd
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.dependencies import require_user, require_vip, access_token_bearer, AccessTokenBearer
from src.exceptions import NotFoundError
from src.auth.service import AuthService
from src.admin.service import AdminService
from src.db.enums import DownloadPermission
from src.db.main import get_session
from src.db.schemas import (
    StorageStatusRead,
    TempFileCreate,
    TempFileRead,
    TempFileUploadResponse,
    FileReadModel,
    TempFilePublicInfo,
    TEMPFS_MAX_LIFETIME,
    TEMPFS_MIN_LIFETIME,
    TEMPFS_DEFAULT_LIFETIME,
)
from src.tempfs.service import TempFSService, _file_path

router = APIRouter(prefix="/tempfs", tags=["tempfs"])
service = TempFSService()
auth_service = AuthService()
admin_service = AdminService()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]

# Optional auth — used on the download endpoint so public files work unauthenticated
optional_token_bearer = Depends(AccessTokenBearer(auto_error=False))


@router.post("/upload", response_model=TempFileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    session: SessionDependency,
    file: UploadFile = File(...),
    download_permission: DownloadPermission = Form(default=DownloadPermission.PUBLIC),
    password: Optional[str] = Form(default=None),
    lifetime_seconds: int = Form(default=TEMPFS_DEFAULT_LIFETIME, ge=TEMPFS_MIN_LIFETIME, le=TEMPFS_MAX_LIFETIME),
    compress: bool = Form(default=True),
    token_details: dict = require_vip,
):
    """
    POST /tempfs/upload
    Upload a file for temporary storage. VIP and Admin only.
    Returns file metadata + updated storage quota.
    """
    metadata = TempFileCreate(
        download_permission=download_permission,
        password=password,
        lifetime_seconds=lifetime_seconds,
        compress=compress,
    )

    return await service.upload(
        file, metadata,
        token_details["user"]["user_id"],
        token_details["user"]["username"],
        session,
    )


@router.get("/files", response_model=list[TempFileRead])
async def list_my_files(
    session: SessionDependency,
    token_details: dict = require_vip,
):
    """
    GET /tempfs/files
    List all active (non-expired) files uploaded by the caller. VIP and Admin only.
    """
    uploader_id = UUID(token_details["user"]["user_id"])
    return await service.list_user_files(uploader_id, session)


@router.get("/storage", response_model=StorageStatusRead)
async def get_storage_status(
    session: SessionDependency,
    token_details: dict = require_vip,
):
    """
    GET /tempfs/storage
    Returns global used/remaining/quota bytes. VIP and Admin only.
    """
    return await service.get_storage_status(session)


@router.get("/files/{file_id}", response_model=TempFilePublicInfo)
async def get_file_info(
    file_id: UUID,
    session: SessionDependency,
    token_details: dict = optional_token_bearer,
):
    """
    GET /tempfs/files/{file_id}
    Returns public metadata for the download page — no auth required for PUBLIC files.
    Returns 404 if the file is not found or has expired.
    """
    info: TempFilePublicInfo = await service.get_public_info(file_id, session)
    if not info:
        raise NotFoundError("File not found or forbidden access")
    return info


@router.get("/files/{file_id}/content")
async def download_file(
    file_id: UUID,
    session: SessionDependency,
    want_compressed: bool = Query(default=False),
    password: Optional[str] = Query(default=None),
    token_details: dict = optional_token_bearer,
):
    """
    GET /tempfs/files/{file_id}/content?want_compressed=false&password=...
    Download a file.
    - public:   no auth required
    - self:     must be the uploader
    - password: must supply correct password (uploader bypasses)
    Auth token is optional — passed if the user is logged in.
    Always returns 404 on any access failure to avoid leaking file existence.
    """
    requester_id: Optional[UUID] = None
    requester_username: Optional[str] = None

    if token_details and await auth_service.is_valid_user_token(token_details, session):
        requester_id = UUID(token_details["user"]["user_id"])
        requester_username = token_details["user"]["username"]

    file: FileReadModel = await service.get_file_for_download(
        file_id,
        requester_id,
        requester_username,
        password,
        want_compressed,
        session,
    )

    if want_compressed and file.is_compressed:
        def _iter_raw():
            with open(file.disk_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

        return StreamingResponse(
            _iter_raw(),
            media_type="application/zstd",
            headers={"Content-Disposition": f'attachment; filename="{file.original_filename}.zst"'},
        )

    elif want_compressed and not file.is_compressed:
        # stream_writer wraps a *destination* writer, not a source — using the
        # source file handle as the destination corrupts the file and crashes.
        # read_to_iter is the correct API: it reads from a file-like source and
        # yields compressed chunks suitable for StreamingResponse.
        def _iter_compress():
            cctx = zstd.ZstdCompressor(level=3)
            with open(file.disk_path, "rb") as f:
                for chunk in cctx.read_to_iter(f):
                    yield chunk

        return StreamingResponse(
            _iter_compress(),
            media_type="application/zstd",
            headers={"Content-Disposition": f'attachment; filename="{file.original_filename}.zst"'},
        )

    elif not want_compressed and file.is_compressed:
        def _iter_decompress():
            dctx = zstd.ZstdDecompressor()
            with open(file.disk_path, "rb") as f:
                with dctx.stream_reader(f) as reader:
                    while chunk := reader.read(1024 * 1024):
                        yield chunk

        return StreamingResponse(
            _iter_decompress(),
            media_type=file.mime_type,
            headers={"Content-Disposition": f'attachment; filename="{file.original_filename}"'},
        )

    else:
        def _iter_plain():
            with open(file.disk_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

        return StreamingResponse(
            _iter_plain(),
            media_type=file.mime_type,
            headers={"Content-Disposition": f'attachment; filename="{file.original_filename}"'},
        )


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: UUID,
    session: SessionDependency,
    token_details: dict = require_user,
):
    """
    DELETE /tempfs/files/{file_id}
    Soft-delete: moves metadata to expired_file, removes from disk.
    Uploader or Admin only (service layer enforces uploader-vs-admin check).
    """
    requester_id = UUID(token_details["user"]["user_id"])
    username = token_details["user"]["username"]

    is_admin = await admin_service.is_user_admin(username, session)

    await service.delete_file(file_id, requester_id, username, is_admin, session)