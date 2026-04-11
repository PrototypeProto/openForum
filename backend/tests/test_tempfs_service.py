"""
tests/test_tempfs_service.py
────────────────────────────
Service-layer tests for TempFSService.

Split into two tiers:

  Pure unit tests (no DB, no Redis)
    — _sanitize_filename edge cases

  Service-layer tests (use `tempfs_svc` + `session` fixtures)
    — get_file_for_download permission branches:
        PUBLIC  (no auth required)
        SELF    (uploader-only, stranger denied, returns 404 not 403)
        PASSWORD (correct pass, wrong pass, uploader bypass)
    — get_public_info (exists, expired, not found)
    — list_user_files (own files only, excludes expired)
    — _used_bytes / _user_used_bytes quota helpers

These tests insert TempFile rows directly via the session — they do NOT
call the upload endpoint, so no real files land on disk. The download tests
create a real temp file on disk so the path-existence check passes.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import generate_passwd_hash
from src.db.enums import DownloadPermission
from src.db.models import TempFile
from src.exceptions import FileNotFoundError as AppFileNotFoundError
from src.tempfs.service import TEMPFS_DIR, _sanitize_filename
from tests.conftest import make_user
from tests.constants import TEST_FILE_PW, TEST_FILE_PW_WRONG, TEST_PASSWORD_STUB

# ══════════════════════════════════════════════════════════════════════════════
# Pure unit tests — _sanitize_filename (no DB, no fixtures)
# ══════════════════════════════════════════════════════════════════════════════


class TestSanitizeFilename:
    def test_normal_filename_unchanged(self):
        assert _sanitize_filename("report.pdf") == "report.pdf"

    def test_none_returns_unnamed(self):
        assert _sanitize_filename(None) == "unnamed"

    def test_empty_string_returns_unnamed(self):
        assert _sanitize_filename("") == "unnamed"

    def test_whitespace_only_returns_unnamed(self):
        assert _sanitize_filename("   ") == "unnamed"

    def test_dots_only_returns_unnamed(self):
        assert _sanitize_filename("...") == "unnamed"

    def test_path_separators_replaced(self):
        result = _sanitize_filename("../../etc/passwd")
        assert "/" not in result
        assert "\\" not in result

    def test_backslash_path_separator_replaced(self):
        result = _sanitize_filename("dir\\file.txt")
        assert "\\" not in result

    def test_control_characters_stripped(self):
        # \x00 is a control character (category Cc)
        result = _sanitize_filename("file\x00name.txt")
        assert "\x00" not in result

    def test_rtl_override_stripped(self):
        # U+202E RIGHT-TO-LEFT OVERRIDE is category Cf
        result = _sanitize_filename("file\u202ename.txt")
        assert "\u202e" not in result

    def test_unicode_filename_preserved(self):
        result = _sanitize_filename("fichier_résumé.pdf")
        assert "résumé" in result

    def test_length_capped_at_200(self):
        long_name = "a" * 300 + ".txt"
        result = _sanitize_filename(long_name)
        assert len(result) <= 200

    def test_custom_max_len_respected(self):
        result = _sanitize_filename("hello_world.txt", max_len=5)
        assert len(result) <= 5

    def test_whitespace_collapsed(self):
        result = _sanitize_filename("my   file   name.txt")
        assert "  " not in result

    def test_nfc_normalisation_applied(self):
        # Decomposed é (U+0065 U+0301) should normalise to composed é (U+00E9)
        import unicodedata

        decomposed = unicodedata.normalize("NFD", "café.txt")
        result = _sanitize_filename(decomposed)
        composed = unicodedata.normalize("NFC", "café.txt")
        assert result == composed


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════


def _future(seconds: int = 3600) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


def _past(seconds: int = 3600) -> datetime:
    return datetime.now(UTC) - timedelta(seconds=seconds)


async def make_tempfile_record(
    session: AsyncSession,
    *,
    uploader_id,
    permission: DownloadPermission = DownloadPermission.PUBLIC,
    password_hash: str | None = None,
    expires_at: datetime | None = None,
    create_disk_file: bool = False,
) -> TempFile:
    """Insert a TempFile metadata row directly, optionally touching a real disk file."""
    file_id = uuid4()
    expires_at = expires_at or _future()

    record = TempFile(
        file_id=file_id,
        uploader_id=uploader_id,
        original_filename="test_file.bin",
        mime_type="application/octet-stream",
        original_size=1024,
        stored_size=1024,
        is_compressed=False,
        download_permission=permission,
        password_hash=password_hash,
        expires_at=expires_at,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    if create_disk_file:
        disk_path = TEMPFS_DIR / str(file_id)
        disk_path.parent.mkdir(parents=True, exist_ok=True)
        disk_path.write_bytes(b"fake content")

    return record


# ══════════════════════════════════════════════════════════════════════════════
# get_file_for_download — permission branches
# ══════════════════════════════════════════════════════════════════════════════


class TestGetFileForDownloadPublic:
    async def test_public_file_no_auth_succeeds(self, tempfs_svc, session: AsyncSession):
        uploader = await make_user(session, username="pubuploader")
        record = await make_tempfile_record(
            session,
            uploader_id=uploader.user_id,
            permission=DownloadPermission.PUBLIC,
            create_disk_file=True,
        )

        result = await tempfs_svc.get_file_for_download(
            record.file_id,
            requester_id=None,
            requester_username=None,
            password=None,
            want_compressed=False,
            session=session,
        )

        assert result.original_filename == "test_file.bin"

        # Cleanup
        (TEMPFS_DIR / str(record.file_id)).unlink(missing_ok=True)

    async def test_expired_file_raises_not_found(self, tempfs_svc, session: AsyncSession):
        uploader = await make_user(session, username="expuploader")
        record = await make_tempfile_record(
            session,
            uploader_id=uploader.user_id,
            permission=DownloadPermission.PUBLIC,
            expires_at=_past(),
        )

        with pytest.raises(AppFileNotFoundError):
            await tempfs_svc.get_file_for_download(
                record.file_id,
                requester_id=None,
                requester_username=None,
                password=None,
                want_compressed=False,
                session=session,
            )

    async def test_nonexistent_file_id_raises_not_found(self, tempfs_svc, session: AsyncSession):
        with pytest.raises(AppFileNotFoundError):
            await tempfs_svc.get_file_for_download(
                uuid4(),
                requester_id=None,
                requester_username=None,
                password=None,
                want_compressed=False,
                session=session,
            )


class TestGetFileForDownloadSelf:
    async def test_uploader_can_download_self_file(self, tempfs_svc, session: AsyncSession):
        uploader = await make_user(session, username="selfuploader")
        record = await make_tempfile_record(
            session,
            uploader_id=uploader.user_id,
            permission=DownloadPermission.SELF,
            create_disk_file=True,
        )

        result = await tempfs_svc.get_file_for_download(
            record.file_id,
            requester_id=uploader.user_id,
            requester_username=uploader.username,
            password=None,
            want_compressed=False,
            session=session,
        )
        assert result is not None

        (TEMPFS_DIR / str(record.file_id)).unlink(missing_ok=True)

    async def test_stranger_denied_with_404_not_403(self, tempfs_svc, session: AsyncSession):
        """SELF files must return 404 (not 403) to avoid leaking file existence."""
        uploader = await make_user(session, username="selfowner")
        stranger = await make_user(session, username="selfstranger")
        record = await make_tempfile_record(
            session,
            uploader_id=uploader.user_id,
            permission=DownloadPermission.SELF,
        )

        with pytest.raises(AppFileNotFoundError):
            await tempfs_svc.get_file_for_download(
                record.file_id,
                requester_id=stranger.user_id,
                requester_username=stranger.username,
                password=None,
                want_compressed=False,
                session=session,
            )

    async def test_unauthenticated_denied(self, tempfs_svc, session: AsyncSession):
        uploader = await make_user(session, username="selfunauth")
        record = await make_tempfile_record(
            session,
            uploader_id=uploader.user_id,
            permission=DownloadPermission.SELF,
        )

        with pytest.raises(AppFileNotFoundError):
            await tempfs_svc.get_file_for_download(
                record.file_id,
                requester_id=None,
                requester_username=None,
                password=None,
                want_compressed=False,
                session=session,
            )


class TestGetFileForDownloadPassword:
    async def test_correct_password_succeeds(self, tempfs_svc, session: AsyncSession):
        uploader = await make_user(session, username="pwuploader")
        pw_hash = generate_passwd_hash(TEST_FILE_PW)
        record = await make_tempfile_record(
            session,
            uploader_id=uploader.user_id,
            permission=DownloadPermission.PASSWORD,
            password_hash=pw_hash,
            create_disk_file=True,
        )

        result = await tempfs_svc.get_file_for_download(
            record.file_id,
            requester_id=None,
            requester_username=None,
            password=TEST_FILE_PW,
            want_compressed=False,
            session=session,
        )
        assert result is not None

        (TEMPFS_DIR / str(record.file_id)).unlink(missing_ok=True)

    async def test_wrong_password_raises_not_found(self, tempfs_svc, session: AsyncSession):
        uploader = await make_user(session, username="pwwrong")
        pw_hash = generate_passwd_hash(TEST_FILE_PW)
        record = await make_tempfile_record(
            session,
            uploader_id=uploader.user_id,
            permission=DownloadPermission.PASSWORD,
            password_hash=pw_hash,
        )

        with pytest.raises(AppFileNotFoundError):
            await tempfs_svc.get_file_for_download(
                record.file_id,
                requester_id=None,
                requester_username=None,
                password=TEST_FILE_PW_WRONG,
                want_compressed=False,
                session=session,
            )

    async def test_uploader_bypasses_password(self, tempfs_svc, session: AsyncSession):
        """Uploader should always be able to download their own file, even without password."""
        uploader = await make_user(session, username="pwbypass")
        pw_hash = generate_passwd_hash(TEST_FILE_PW)
        record = await make_tempfile_record(
            session,
            uploader_id=uploader.user_id,
            permission=DownloadPermission.PASSWORD,
            password_hash=pw_hash,
            create_disk_file=True,
        )

        result = await tempfs_svc.get_file_for_download(
            record.file_id,
            requester_id=uploader.user_id,
            requester_username=uploader.username,
            password=None,  # no password supplied
            want_compressed=False,
            session=session,
        )
        assert result is not None

        (TEMPFS_DIR / str(record.file_id)).unlink(missing_ok=True)

    async def test_no_password_supplied_raises_not_found(self, tempfs_svc, session: AsyncSession):
        uploader = await make_user(session, username="pwnopass")
        pw_hash = generate_passwd_hash(TEST_FILE_PW)
        record = await make_tempfile_record(
            session,
            uploader_id=uploader.user_id,
            permission=DownloadPermission.PASSWORD,
            password_hash=pw_hash,
        )

        with pytest.raises(AppFileNotFoundError):
            await tempfs_svc.get_file_for_download(
                record.file_id,
                requester_id=None,
                requester_username=None,
                password=None,
                want_compressed=False,
                session=session,
            )


# ══════════════════════════════════════════════════════════════════════════════
# get_public_info
# ══════════════════════════════════════════════════════════════════════════════


class TestGetPublicInfo:
    async def test_returns_info_for_active_file(self, tempfs_svc, session: AsyncSession):
        uploader = await make_user(session, username="infouploader")
        record = await make_tempfile_record(session, uploader_id=uploader.user_id)

        info = await tempfs_svc.get_public_info(record.file_id, session)

        assert info is not None
        assert info.file_id == record.file_id
        assert info.original_filename == "test_file.bin"

    async def test_returns_none_for_expired_file(self, tempfs_svc, session: AsyncSession):
        uploader = await make_user(session, username="expinfo")
        record = await make_tempfile_record(
            session, uploader_id=uploader.user_id, expires_at=_past()
        )

        info = await tempfs_svc.get_public_info(record.file_id, session)
        assert info is None

    async def test_returns_none_for_unknown_file(self, tempfs_svc, session: AsyncSession):
        info = await tempfs_svc.get_public_info(uuid4(), session)
        assert info is None

    async def test_requires_password_flag_set_correctly(self, tempfs_svc, session: AsyncSession):
        uploader = await make_user(session, username="pwflaguploader")
        record = await make_tempfile_record(
            session,
            uploader_id=uploader.user_id,
            permission=DownloadPermission.PASSWORD,
            password_hash=generate_passwd_hash(TEST_PASSWORD_STUB),
        )

        info = await tempfs_svc.get_public_info(record.file_id, session)
        assert info.requires_password is True

    async def test_requires_password_false_for_public(self, tempfs_svc, session: AsyncSession):
        uploader = await make_user(session, username="nopwflag")
        record = await make_tempfile_record(
            session,
            uploader_id=uploader.user_id,
            permission=DownloadPermission.PUBLIC,
        )

        info = await tempfs_svc.get_public_info(record.file_id, session)
        assert info.requires_password is False


# ══════════════════════════════════════════════════════════════════════════════
# list_user_files
# ══════════════════════════════════════════════════════════════════════════════


class TestListUserFiles:
    async def test_returns_own_files_only(self, tempfs_svc, session: AsyncSession):
        owner = await make_user(session, username="listowner")
        other = await make_user(session, username="listother")

        await make_tempfile_record(session, uploader_id=owner.user_id)
        await make_tempfile_record(session, uploader_id=owner.user_id)
        await make_tempfile_record(session, uploader_id=other.user_id)

        files = await tempfs_svc.list_user_files(owner.user_id, session)
        assert len(files) == 2

    async def test_excludes_expired_files(self, tempfs_svc, session: AsyncSession):
        owner = await make_user(session, username="listexpired")

        await make_tempfile_record(session, uploader_id=owner.user_id)  # active
        await make_tempfile_record(
            session, uploader_id=owner.user_id, expires_at=_past()
        )  # expired

        files = await tempfs_svc.list_user_files(owner.user_id, session)
        assert len(files) == 1

    async def test_empty_when_no_files(self, tempfs_svc, session: AsyncSession):
        owner = await make_user(session, username="listempty")
        files = await tempfs_svc.list_user_files(owner.user_id, session)
        assert files == []

    async def test_ordered_by_expiry_ascending(self, tempfs_svc, session: AsyncSession):
        owner = await make_user(session, username="listorder")

        soon = await make_tempfile_record(
            session,
            uploader_id=owner.user_id,
            expires_at=_future(600),
        )
        later = await make_tempfile_record(
            session,
            uploader_id=owner.user_id,
            expires_at=_future(7200),
        )

        files = await tempfs_svc.list_user_files(owner.user_id, session)
        assert files[0].file_id == soon.file_id
        assert files[1].file_id == later.file_id


# ══════════════════════════════════════════════════════════════════════════════
# Quota helpers — _used_bytes, _user_used_bytes
# ══════════════════════════════════════════════════════════════════════════════


class TestQuotaHelpers:
    async def test_used_bytes_sums_all_stored_sizes(self, tempfs_svc, session: AsyncSession):
        u1 = await make_user(session, username="quota1")
        u2 = await make_user(session, username="quota2")

        r1 = await make_tempfile_record(session, uploader_id=u1.user_id)
        r2 = await make_tempfile_record(session, uploader_id=u2.user_id)

        total = await tempfs_svc._used_bytes(session)
        # Both records have stored_size=1024
        assert total >= 2048

    async def test_user_used_bytes_scoped_to_uploader(self, tempfs_svc, session: AsyncSession):
        owner = await make_user(session, username="usedbytes_owner")
        other = await make_user(session, username="usedbytes_other")

        await make_tempfile_record(session, uploader_id=owner.user_id)
        await make_tempfile_record(session, uploader_id=owner.user_id)
        await make_tempfile_record(session, uploader_id=other.user_id)

        owner_bytes = await tempfs_svc._user_used_bytes(owner.user_id, session)
        assert owner_bytes == 2048  # exactly 2 × 1024

    async def test_user_used_bytes_zero_for_new_user(self, tempfs_svc, session: AsyncSession):
        fresh = await make_user(session, username="zerobytes")
        used = await tempfs_svc._user_used_bytes(fresh.user_id, session)
        assert used == 0
