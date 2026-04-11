import math
from pathlib import Path

from src.config import Config
from src.db.schemas import PaginatedMedia

ALLOWED_EXTENSIONS = {".mp4", ".jpg", ".jpeg", ".png"}


class MediaService:
    async def list_accessible_media(self, page: int, limit: int) -> PaginatedMedia:
        all_files = sorted(
            f.name
            for f in Path(Config.MEDIA_DIR).iterdir()
            if f.suffix.lower() in ALLOWED_EXTENSIONS
        )

        total = len(all_files)
        pages = math.ceil(total / limit) if total > 0 else 1
        offset = (page - 1) * limit

        return PaginatedMedia(
            items=all_files[offset : offset + limit],
            total=total,
            page=page,
            page_size=limit,
            pages=pages,
        )


# ---------------------------------------------------------------------------
# Module-level singleton — import this instead of instantiating MediaService()
# ---------------------------------------------------------------------------

media_service = MediaService()
