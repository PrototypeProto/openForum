from src.db.models import *
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, desc, delete, update, insert
from datetime import date, datetime
from uuid import UUID
from src.auth.service import AuthService
from typing import List, Tuple
from pathlib import Path
from src.config import Config

auth_service = AuthService()


ALLOWED_EXTENSIONS = {".mp4", ".jpg", ".jpeg", ".png"}

class MediaService:
    async def list_accessible_media(self, page: int, limit: int):
        files = [f.name for f in Path(Config.MEDIA_DIR).iterdir() if f.suffix.lower() in ALLOWED_EXTENSIONS] # this is already simple enough to live in the router
        return files[page*limit : page*limit + limit]
    