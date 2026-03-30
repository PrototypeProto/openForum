import redis.asyncio as redis
from src.config import Config
from datetime import timedelta
from src.db.db_models import MemberRoleEnum

ROLE_EXPIRY = timedelta(weeks=1)


redis_user_role = redis.Redis(
    host=Config.REDIS_HOST,
    port=Config.REDIS_PORT,
    db=1
)


async def set_user_role(username: str, role: MemberRoleEnum) -> None:
    await redis_user_role.set(
        name=username,
        value=role,
        ex=int(ROLE_EXPIRY.total_seconds()) if role == MemberRoleEnum.USER else None
    )

async def get_user_role(username: str) -> MemberRoleEnum | None:
    role: bytes = await redis_user_role.get(username)
    return None if role is None else MemberRoleEnum(role.decode())

    