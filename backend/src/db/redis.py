import redis
from src.config import Config

JTI_EXPIRY = 3600


redis_token_blocklist = redis.StrictRedis(
    host=Config.REDIS_HOST,
    port=Config.REDIS_PORT,
    db=0
)

async def add_jti_to_blocklist(jti:str) -> None:
    redis_token_blocklist.set(
        name=jti,
        value="",
        ex=JTI_EXPIRY
    )

async def token_in_blocklist(jti:str) -> bool:
    jti_token = redis_token_blocklist.get(jti)

    return jti_token is not None
    