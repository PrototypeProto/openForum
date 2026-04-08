"""
/tempfs routes
VIP and Admin only for upload. Download access depends on file permission setting.
"""
import io
from typing import Annotated, Optional
from uuid import UUID

import zstandard as zstd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.dependencies import access_token_bearer, AccessTokenBearer
from src.auth.service import AuthService
from src.admin.service import AdminService
from src.db.db_models import MemberRoleEnum, DownloadPermission
from src.db.main import get_session
from src.db.read_models import (
    StorageStatusRead,
    TempFileCreate,
    TempFileRead,
    TempFileUploadResponse,
    FileReadModel,
    TempFilePublicInfo,
    MAX_LIFETIME,
    MIN_LIFETIME,
    DEFAULT_LIFETIME
)
from src.tempfs.service import TempFSService, _file_path

router = APIRouter(prefix="/tempfs", tags=["tempfs"])
service = TempFSService()
auth_service = AuthService()
admin_service = AdminService()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]

# Optional auth — used on the download endpoint so public files work unauthenticated
optional_token_bearer = Depends(AccessTokenBearer(auto_error=False))


# Upload 
@router.post("/upload", response_model=TempFileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    session: SessionDependency,
    file: UploadFile = File(...),
    download_permission: DownloadPermission = Form(default=DownloadPermission.PUBLIC),
    password: Optional[str] = Form(default=None),
    lifetime_seconds: int = Form(default=DEFAULT_LIFETIME, ge=MIN_LIFETIME, le=MAX_LIFETIME),
    compress: bool = Form(default=True),
    token_details: dict = access_token_bearer,
):
    """
    POST /tempfs/upload
    Upload a file for temporary storage.
    VIP and Admin only.
    Returns file metadata + updated storage quota.
    """
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    username = token_details["user"]["username"]

    try:
        await service.is_valid_uploader(username)
    except:
        raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="VIP or Admin access required",
            )

    metadata = TempFileCreate(
        download_permission=download_permission,
        password=password,
        lifetime_seconds=lifetime_seconds,
        compress=compress,
    )

    try:
        return await service.upload(file, metadata, token_details["user"]["user_id"], username, session)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# List active uploads for this user
@router.get("/files", response_model=list[TempFileRead])
async def list_my_files(
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    """
    GET /tempfs/files
    List all active (non-expired) files uploaded by the caller.
    VIP and Admin only.
    """
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    try:
        await service.is_valid_uploader(token_details['user']['username'])
    except:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient perms")

    uploader_id = UUID(token_details["user"]["user_id"])
    return await service.list_user_files(uploader_id, session)


# Storage status
@router.get("/storage", response_model=StorageStatusRead)
async def get_storage_status(
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    """
    GET /tempfs/storage
    Returns global used/remaining/quota bytes.
    VIP and Admin only.
    """
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        await service.is_valid_uploader(token_details['user']['username'])
    except:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient perms")


    return await service.get_storage_status(session)


# Public file info (no auth required)
@router.get("/files/{file_id}", response_model=TempFilePublicInfo)
async def get_file_info(file_id: UUID, session: SessionDependency, token_details: dict = optional_token_bearer):
    """
    GET /tempfs/info/{file_id}
    Returns public metadata for the download page — no auth required IF info.download_permission is PUBLIC.
    Returns 404 if file is not found or has expired.
    Does not reveal uploader identity or password hash.
    NOTE: Implement identity checking if not a public file
    """
    info: TempFilePublicInfo = await service.get_public_info(file_id, session)
    if not info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found or forbidden access")
    return info


# Download
@router.get("/files/{file_id}/content")
async def download_file(
    file_id: UUID,
    session: SessionDependency,
    want_compressed: bool = Query(default=False),
    password: Optional[str] = Query(default=None),
    token_details: dict = optional_token_bearer,
):
    """
    GET /tempfs/download/{file_id}?want_compressed=false&password=...
    Download a file.
    - public:   no auth required
    - self:     must be the uploader
    - password: must supply correct password (uploader bypasses)
    Auth token is optional — passed if the user is logged in.
    Always returns 404 on any access failure to avoid leaking file existence.
    NOTE: crashed when want_compressed is true
    """
    # Resolve optional caller identity
    requester_id: Optional[UUID] = None
    requester_username: Optional[str] = None

    if token_details and await auth_service.is_valid_user_token(token_details, session):
        requester_id = UUID(token_details["user"]["user_id"])
        requester_username = token_details["user"]["username"]

    try:
        file: FileReadModel = (
            await service.get_file_for_download(
                file_id,
                requester_id,
                requester_username,
                password,
                want_compressed,
                session,
            )
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Determine how to serve the file
    if want_compressed and file.is_compressed:
        # Stored file is already zstd — serve directly
        content_type = "application/zstd"
        download_name = file.original_filename + ".zst"

        def _iter_raw():
            with open(file.disk_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

        return StreamingResponse(
            _iter_raw(),
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
        )

    elif want_compressed and not file.is_compressed:
        # Stored file is uncompressed — compress on the fly
        content_type = "application/zstd"
        download_name = file.original_filename + ".zst"

        def _iter_compress():
            cctx = zstd.ZstdCompressor(level=3)
            with open(file.disk_path, "rb") as f:
                with cctx.stream_writer(f, closefd=False) as compressor:
                    while chunk := f.read(1024 * 1024):
                        yield compressor.write(chunk)

        return StreamingResponse(
            _iter_compress(),
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
        )

    elif not want_compressed and file.is_compressed:
        # Stored file is zstd — decompress on the fly
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
        # Stored uncompressed, serving original — plain stream
        def _iter_plain():
            with open(file.disk_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

        return StreamingResponse(
            _iter_plain(),
            media_type=file.mime_type,
            headers={"Content-Disposition": f'attachment; filename="{file.original_filename}"'},
        )


# Delete 
@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: UUID,
    session: SessionDependency,
    token_details: dict = access_token_bearer,
):
    """
    DELETE /tempfs/files/{file_id}
    Soft-delete: moves metadata to expired_file, removes from disk.
    Uploader or Admin only.
    """
    if not await auth_service.is_valid_user_token(token_details, session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    requester_id = UUID(token_details["user"]["user_id"])
    username = token_details["user"]["username"]
    is_admin = await admin_service.verify_admin(token_details, session)

    try:
        await service.delete_file(file_id, requester_id, username, is_admin, session)
        if await service.get_public_info(file_id, session):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="failed to delete file")
        if _file_path(file_id):
            print("failed to del file")
            raise Exception("file not deleted")
    except ValueError as e:
        if str(e) == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
