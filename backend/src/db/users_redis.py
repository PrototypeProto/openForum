import redis.asyncio as redis
from src.config import Config
from datetime import timedelta
from src.db.db_models import MemberRoleEnum

USER_EXPIRY = None


redis_user = redis.Redis(
    host=Config.REDIS_HOST,
    port=Config.REDIS_PORT,
    db=2
)


async def add_registered_user(username: str, is_member: bool = True) -> None:
    await redis_user.set(
        name=username,
        value="1",
        ex=USER_EXPIRY
    )

async def get_user(username: str) -> MemberRoleEnum | None:
    role:bytes = await redis_user.get(username)
    return None if role is None else role.decode()

async def remove_user(username: str) -> None:
    await redis_user.delete(username)
    
