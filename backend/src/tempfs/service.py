"""
TempFS service — handles all business logic for /tempfs.
Files are stored on disk at {TEMPFS_DIR}/{file_id} (no extension, UUID name only).
Compression uses zstd; we only keep the compressed version if it is smaller.
"""
import os
import shutil
from datetime import datetime, timezone, timedelta
from math import ceil
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

import zstandard as zstd
from fastapi import UploadFile
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import generate_passwd_hash, verify_passwd
from src.config import Config
from src.db.enums import DownloadPermission, MemberRoleEnum
from src.db.models import TempFile, ExpiredFile
from src.db.schemas import (
    TEMPFS_MIN_LIFETIME,
    TEMPFS_MAX_LIFETIME,
    TEMPFS_DEFAULT_LIFETIME,
    TempFileRead,
    TempFileUploadResponse,
    StorageStatusRead,
    TempFileCreate,
    TempFilePublicInfo,
    FileReadModel,
)
from src.tempfs.logger import (
    log_upload_ok,
    log_upload_fail,
    log_download_ok,
    log_download_fail,
    log_delete_ok,
    log_manual_delete_fail,
    log_expire,
    log_cleanup_delete_fail,
    log_cleanup_delete_ok,
)
from src.db.redis_client import get_user
from src.exceptions import (
    BadRequestError,
    FileTooLargeError,
    QuotaExceededError,
    InvalidPasswordError,
    NotFoundError,
    ForbiddenError,
    FileNotFoundError as AppFileNotFoundError,
    InternalError,
)

TEMPFS_DIR = Path(Config.TEMPFS_DIR)
TOTAL_SHARED_BYTES = 200 * 1024 ** 3          # 200 GB global quota
USER_QUOTA_BYTES = 5 * 1024 ** 3          # 5 GB per-user quota
MAX_FILE_SIZE = 2 * 1024 ** 3        # 2 GB per file
CHUNK = 1024 * 1024                  # 1 MB read chunks


def _file_path(file_id: UUID) -> Path:
    print(TEMPFS_DIR)
    return TEMPFS_DIR / str(file_id)


def _ensure_dir() -> None:
    TEMPFS_DIR.mkdir(parents=True, exist_ok=True)


class TempFSService:

    # helpers 
    async def _used_bytes(self, session: AsyncSession) -> int:
        """Total stored_size across all active temp files."""
        result = await session.exec(select(func.sum(TempFile.stored_size)))
        return result.one() or 0

    async def _user_used_bytes(self, uploader_id: UUID, session: AsyncSession) -> int:
        result = await session.exec(
            select(func.sum(TempFile.stored_size))
            .where(TempFile.uploader_id == uploader_id)
        )
        return result.one() or 0

    def _is_vip_or_admin(self, role: str) -> bool:
        return role in (MemberRoleEnum.VIP.value, MemberRoleEnum.ADMIN.value)

    def _bytes_to_MB(self, file_size: int) -> str:
        return f'{file_size / 1024 / 1024} MB'

    # upload file from this user
    async def upload(
        self,
        file: UploadFile,
        metadata: TempFileCreate,
        uploader_id: UUID,
        username: str,
        session: AsyncSession,
    ) -> TempFileUploadResponse:
        _ensure_dir()

        # Validate permission + password consistency
        perm = DownloadPermission(metadata.download_permission)
        if perm == DownloadPermission.PASSWORD and not metadata.password:
            log_upload_fail(username, "password_permission_requires_password")
            raise InvalidPasswordError("A password is required when permission is 'password'")

        # Clamp lifetime
        lifetime = max(TEMPFS_MIN_LIFETIME, min(metadata.lifetime_seconds, TEMPFS_MAX_LIFETIME))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=lifetime)

        # Read full file into memory to get size before touching disk
        # (We need size upfront to check quota; 2GB max is within acceptable RAM for a personal server)
        raw: bytes = await file.read()
        file_size = len(raw)

        if file_size > MAX_FILE_SIZE:
            log_upload_fail(username, "file_too_large", {
                "file_size": file_size,
                "max_size": MAX_FILE_SIZE,
            })
            raise FileTooLargeError(f"File exceeds 2 GB limit ({self._bytes_to_MB(file_size)})")

        # Check global quota BEFORE writing anything
        system_bytes_used = await self._used_bytes(session)
        if system_bytes_used + file_size > TOTAL_SHARED_BYTES:
            log_upload_fail(username, "quota_exceeded", {
                "used_bytes": system_bytes_used,
                "file_size": file_size,
                "total_bytes_offered": TOTAL_SHARED_BYTES,
            })
            raise QuotaExceededError(
                f"Upload would exceed global storage quota. "
                f"Used: {self._bytes_to_MB(system_bytes_used)}, file: {self._bytes_to_MB(file_size)}, quota: {self._bytes_to_MB(TOTAL_SHARED_BYTES)}"
            )

        # Check if user exceeds their own limit
        user_bytes_used = file_size + await self._user_used_bytes(uploader_id, session)
        if user_bytes_used > USER_QUOTA_BYTES:
            log_upload_fail(username, "quota_exceeded", {
                "used_bytes": user_bytes_used,
                "file_size": file_size,
                "quota": USER_QUOTA_BYTES,
            })
            raise QuotaExceededError(
                f"Upload would exceed assigned user storage quota. "
                f"Used: {self._bytes_to_MB(user_bytes_used)}, file: {self._bytes_to_MB(file_size)}, quota: {self._bytes_to_MB(USER_QUOTA_BYTES)}"
            )

        # Attempt compression if requested
        file_id = uuid4() # NOTE: Let DB handle uuid assignment
        dest = _file_path(file_id)
        is_compressed = False
        stored_data = raw

        if metadata.compress:
            cctx = zstd.ZstdCompressor(level=3)
            compressed = cctx.compress(raw)
            if len(compressed) < file_size:
                stored_data = compressed
                is_compressed = True

        stored_size = len(stored_data)

        # Write to disk
        dest.write_bytes(stored_data)

        # Hash password if applicable AND when PASSWORD protected (ignores password w/ other options)
        password_hash: Optional[str] = None
        if perm == DownloadPermission.PASSWORD and metadata.password:
            password_hash = generate_passwd_hash(metadata.password)


        # Persist metadata
        record = TempFile(
            file_id=file_id,
            uploader_id=uploader_id,
            original_filename=file.filename or "unnamed",
            mime_type=file.content_type or "application/octet-stream",
            original_size=file_size,
            stored_size=stored_size,
            is_compressed=is_compressed,
            download_permission=perm,
            password_hash=password_hash,
            expires_at=expires_at,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)

        new_used_bytes = await self._user_used_bytes(uploader_id, session)
        log_upload_ok(
            username, str(file_id), file.filename or "unnamed",
            file_size, stored_size, is_compressed, expires_at,
        )

        return TempFileUploadResponse(
            file_id=file_id,
            original_filename=record.original_filename,
            original_size=file_size,
            stored_size=stored_size,
            is_compressed=is_compressed,
            expires_at=expires_at,
            download_permission=perm.value,
            used_bytes=new_used_bytes,
            remaining_bytes=USER_QUOTA_BYTES - new_used_bytes,
        )

    # list unexpired files for this user
    async def list_user_files(
        self, uploader_id: UUID, session: AsyncSession
    ) -> list[TempFileRead]:
        now = datetime.now(timezone.utc)
        result = await session.exec(
            select(TempFile)
            .where(TempFile.uploader_id == uploader_id)
            .where(TempFile.expires_at > now)
            .order_by(TempFile.expires_at.asc())
        )
        rows = result.all()
        return [
            TempFileRead(
                file_id=r.file_id,
                original_filename=r.original_filename,
                mime_type=r.mime_type,
                original_size=r.original_size,
                stored_size=r.stored_size,
                is_compressed=r.is_compressed,
                download_permission=r.download_permission.value,
                created_at=r.created_at,
                expires_at=r.expires_at,
            )
            for r in rows
        ]

    # system storage status
    async def get_storage_status(self, session: AsyncSession) -> StorageStatusRead:
        used = await self._used_bytes(session)
        return StorageStatusRead(
            used_bytes=used,
            remaining_bytes=max(0, TOTAL_SHARED_BYTES - used),
            storage_cap_bytes=TOTAL_SHARED_BYTES,
        )

    # download 
    async def get_file_for_download(
        self,
        file_id: UUID,
        requester_id: Optional[UUID],
        requester_username: Optional[str],
        password: Optional[str],
        want_compressed: bool,
        session: AsyncSession,
    ) -> FileReadModel:
        """
        Validates access and returns (disk_path, original_filename, mime_type, serve_compressed).
        Raises ValueError with a reason string on any access failure.
        The caller should catch ValueError and return 404 (not 403, to avoid leaking existence).
        TODO NOTE: want_compressed does nothing. Ensure that a compressed file is decompressed when want_compressed=false, or a decompressed file is compressed if want_compressed=True
        """
        now = datetime.now(timezone.utc)
        record: TempFile = await session.get(TempFile, file_id)

        if not record or record.expires_at <= now:
            reason = "not_found_or_expired"
            log_download_fail(requester_username, str(file_id), reason)
            raise AppFileNotFoundError(reason)

        perm_required = record.download_permission

        # Permission checks
        if perm_required == DownloadPermission.SELF:
            if requester_id is None or requester_id != record.uploader_id:
                reason = "permission_denied"
                log_download_fail(requester_username, str(file_id), reason)
                raise AppFileNotFoundError(reason)

        elif perm_required == DownloadPermission.PASSWORD:
            # Uploader always bypasses password
            is_owner = requester_id is not None and requester_id == record.uploader_id
            if not is_owner:
                if not password or not verify_passwd(password, record.password_hash):
                    reason = "invalid_password"
                    log_download_fail(requester_username, str(file_id), reason)
                    raise AppFileNotFoundError(reason)

        # perm == PUBLIC: no further checks needed

        disk_path: Path = _file_path(file_id)
        if not disk_path.exists():
            reason = "file_missing_from_disk"
            log_download_fail(requester_username, str(file_id), reason)
            raise AppFileNotFoundError(reason)

        log_download_ok(requester_username, str(file_id), record.original_filename)
        return FileReadModel(disk_path=disk_path, original_filename=record.original_filename, mime_type=record.mime_type, is_compressed=record.is_compressed)

    # delete (user-initiated)
    async def delete_file(
        self,
        file_id: UUID,
        requester_id: UUID,
        username: str,
        is_admin: bool,
        session: AsyncSession,
    ) -> None:
        record = await session.get(TempFile, file_id)
        if not record:
            log_manual_delete_fail(username, str(file_id), "not_found")
            raise NotFoundError("File not found")

        if not is_admin and record.uploader_id != requester_id:
            log_manual_delete_fail(username, str(file_id), "permission_denied")
            raise ForbiddenError("You do not have permission to delete this file")

        await self._move_to_expired(record, session)
        log_delete_ok(username, str(file_id), record.original_filename)

    # expiry (called by scheduler)
    async def expire_due_files(self, session: AsyncSession) -> int:
        """
        Deletes all TempFile files whose expires_at <= now.
        Moves metadata to expired_file, deletes disk file.
        Returns count of files deleted.
        """
        now = datetime.now(timezone.utc)
        result = await session.exec(
            select(TempFile).where(TempFile.expires_at <= now)
        )
        due = result.all()

        for record in due:
            log_expire(
                str(record.file_id),
                str(record.uploader_id),
                record.original_filename,
                record.expires_at,
            )
            await self._move_to_expired(record, session)

        return len(due)

    async def _move_to_expired(self, record: TempFile, session: AsyncSession) -> None:
        """
        Atomically: delete disk file, insert into expired_file, delete from temp_file.
        Order matters — disk first so a crash after disk delete but before DB commit
        leaves an orphan row in temp_file (recoverable) rather than a dangling DB row.
        """
        disk_path = _file_path(record.file_id)
        print(disk_path)
        try:
            disk_path.unlink(missing_ok=True)
            if disk_path.exists():
                raise InternalError("Deleted file still exists on disk")
            log_cleanup_delete_ok(record.file_id)
        except OSError as e:
            log_cleanup_delete_fail(record.file_id, e)
            pass  # already gone; still archive the metadata
        except Exception as e:
            log_cleanup_delete_fail(record.file_id, e)
            pass  # already gone; still archive the metadata
            

        expired = ExpiredFile(
            file_id=record.file_id,
            uploader_id=record.uploader_id,
            original_filename=record.original_filename,
            mime_type=record.mime_type,
            original_size=record.original_size,
            stored_size=record.stored_size,
            is_compressed=record.is_compressed,
            download_permission=record.download_permission,
            password_hash=record.password_hash,
            created_at=record.created_at,
            expires_at=record.expires_at,
        )
        session.add(expired)
        await session.delete(record)
        await session.commit()


    async def get_public_info(
        self, file_id: UUID, session: AsyncSession
    ) -> TempFilePublicInfo:
        """
        Returns public metadata for the download page.
        Returns None if the file doesn't exist or has expired.
        """
        now = datetime.now(timezone.utc)
        record = await session.get(TempFile, file_id)
        if not record or record.expires_at <= now:
            return None
        return TempFilePublicInfo(
            file_id=record.file_id,
            original_filename=record.original_filename,
            original_size=record.original_size,
            stored_size=record.stored_size,
            is_compressed=record.is_compressed,
            download_permission=record.download_permission.value,
            expires_at=record.expires_at,
            requires_password=record.download_permission == DownloadPermission.PASSWORD,
        )