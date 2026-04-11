"""
TempFS logger — plain text action lines with optional JSON detail indented below.
Rotates weekly (Mon-Sun) into logs/tempfs/YYYY-WNN.log
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from src.config import Config

LOGS_DIR = Path(Config.LOGS_DIR)

LOG_DIR: Path = LOGS_DIR / "tempfs"


def _log_path() -> Path:
    now = datetime.now(UTC)
    # isocalendar(): (year, week_number, weekday)
    year, week, _ = now.isocalendar()
    return LOG_DIR / f"{year}-W{week:02d}.log"


def _write(line: str, detail: dict | None = None) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = _log_path()
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        if detail:
            f.write("  " + json.dumps(detail) + "\n")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


# ── Public helpers ──────────────────────────────────────────────────────────


def log_upload_ok(
    username: str,
    file_id: str,
    original_filename: str,
    original_size: int,
    stored_size: int,
    is_compressed: bool,
    expires_at: datetime,
) -> None:
    line = (
        f"[{_now()}] UPLOAD OK | user={username} file_id={file_id} "
        f"original={original_filename} "
        f"size={original_size}B stored={stored_size}B compressed={is_compressed}"
    )
    _write(
        line,
        {
            "file_id": file_id,
            "uploader": username,
            "original_filename": original_filename,
            "original_size": original_size,
            "stored_size": stored_size,
            "is_compressed": is_compressed,
            "expires_at": expires_at.isoformat(),
        },
    )


def log_upload_fail(username: str, reason: str, detail: dict | None = None) -> None:
    line = f"[{_now()}] UPLOAD FAIL | user={username} reason={reason}"
    _write(line, detail)


def log_download_ok(username: str | None, file_id: str, original_filename: str) -> None:
    who = username or "anonymous"
    line = f"[{_now()}] DOWNLOAD OK | user={who} file_id={file_id} file={original_filename}"
    _write(line)


def log_download_fail(username: str | None, file_id: str, reason: str) -> None:
    who = username or "anonymous"
    line = f"[{_now()}] DOWNLOAD FAIL | user={who} file_id={file_id} reason={reason}"
    _write(line)


def log_delete_ok(
    username: str,
    file_id: str,
    original_filename: str,
    reason: str = "user_request",
) -> None:
    line = (
        f"[{_now()}] DELETE OK | user={username} file_id={file_id} "
        f"file={original_filename} reason={reason}"
    )
    _write(line)


def log_manual_delete_fail(username: str, file_id: str, reason: str) -> None:
    line = f"[{_now()}] DELETE FAIL | user={username} file_id={file_id} reason={reason}"
    _write(line)


def log_cleanup_delete_fail(file_id: str, reason: str) -> None:
    line = f"[{_now()}] DELETE FAIL during attempted automatic cleaning session | file_id={file_id} reason={reason}"
    _write(line)


def log_cleanup_delete_ok(file_id: str) -> None:
    line = f"[{_now()}] DELETED {file_id} STATUS: `OK` during schedules cleaning session"
    _write(line)


def log_expire(
    file_id: str,
    uploader_id: str,
    original_filename: str,
    expired_at: datetime,
) -> None:
    line = (
        f"[{_now()}] EXPIRE | file_id={file_id} uploader={uploader_id} "
        f"file={original_filename} expired_at={expired_at.isoformat()}"
    )
    _write(
        line,
        {
            "file_id": file_id,
            "uploader_id": uploader_id,
            "original_filename": original_filename,
            "expired_at": expired_at.isoformat(),
            "deleted_at": _now(),
        },
    )
