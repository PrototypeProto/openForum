from bcrypt import hashpw, checkpw, gensalt
import jwt
from jwt.exceptions import ExpiredSignatureError
from src.config import Config
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import logging

logger = logging.getLogger("portfolio.auth")
logger.setLevel(Config.log_level)

# Access token: 75 minutes
ACCESS_TOKEN_EXPIRY_SECONDS = 60 * 75

# Refresh token: 7 days
REFRESH_TOKEN_EXPIRY_SECONDS = 60 * 60 * 24 * 7


def generate_passwd_hash(password: str) -> str:
    return hashpw(password.encode("utf-8"), gensalt()).decode("utf-8")


def verify_passwd(plain_password: str, hashed_password: str) -> bool:
    return checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(
    user_data: dict,
    expiry_seconds: int = ACCESS_TOKEN_EXPIRY_SECONDS,
    refresh: bool = False,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user": user_data,
        "exp": now + timedelta(seconds=expiry_seconds),
        "iat": now,
        "jti": str(uuid4()),
        "refresh": refresh,
    }
    return jwt.encode(
        payload=payload,
        key=Config.JWT_SECRET,
        algorithm=Config.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict | None:
    """
    Decode and verify a JWT.

    Returns the payload dict on success, or None if the token is expired,
    malformed, or otherwise invalid. Never raises — callers check for None.
    """
    try:
        return jwt.decode(
            jwt=token,
            key=Config.JWT_SECRET,
            algorithms=[Config.JWT_ALGORITHM],
        )
    except ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except jwt.PyJWTError as e:
        logger.debug("JWT decode error: %s", e)
        return None


def seconds_until_expiry(token_data: dict) -> int:
    """Returns the remaining lifetime of a token in whole seconds (min 0)."""
    exp = token_data.get("exp", 0)
    remaining = exp - int(datetime.now(timezone.utc).timestamp())
    return max(remaining, 0)
