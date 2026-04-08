"""
TempFS cleanup scheduler.
Runs every 30 minutes, deletes expired files from disk and moves metadata to expired_file.
Uses APScheduler AsyncIOScheduler so it lives inside the FastAPI process and
survives container restarts (the schedule is code, not state).
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.db.main import get_session_context
from src.tempfs.service import TempFSService
from src.tempfs.logger import _write, _now

_scheduler = AsyncIOScheduler()
_service = TempFSService()


async def _run_cleanup() -> None:
    print("RUNNING disk cleanup")
    _write(line=f"{_now()} | Running disk cleanup")
    async with get_session_context() as session:
        count = await _service.expire_due_files(session)
        if count:
            _write(line=f'{_now()} | Cleaned up `{count}` files')
        else: 
            _write(line=f'{_now()} | No files required to be cleaned up')


def start_scheduler() -> None:
    _scheduler.add_job(
        _run_cleanup,
        trigger=IntervalTrigger(minutes=30),
        id="tempfs_cleanup",
        replace_existing=True,
        max_instances=1,       # prevent overlapping runs
    )
    _scheduler.start()


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)