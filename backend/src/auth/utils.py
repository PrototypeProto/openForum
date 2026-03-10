from bcrypt import hashpw, checkpw, gensalt
import jwt
from src.config import Config
from datetime import datetime, timedelta
from uuid import uuid4
import logging

# 3600 sec -> 60 min -> 1 hr
ACCESS_TOKEN_EXPIRY = 3

# Hash a password using bcrypt
def generate_passwd_hash(password) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = gensalt()
    hashed_password = hashpw(pwd_bytes, salt)
    return hashed_password.decode("utf-8")

# Check if the provided password matches the stored password (hashed)
def verify_passwd(plain_password, hashed_password) -> bool:
    return checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(user_data: dict, expiry: timedelta = None, refresh: bool = False) -> str:
    payload = {}

    payload["user"] = user_data
    payload["exp"] = datetime.now() + (expiry if expiry is not None else timedelta(days=ACCESS_TOKEN_EXPIRY))
    payload["jti"] = str(uuid4())
    # Has refresh token
    payload["refresh"] = refresh

    token = jwt.encode(
        payload=payload,
        key=Config.JWT_SECRET,
        algorithm=Config.JWT_ALGORITHM,
    )

    return token


def decode_token(token: str) -> dict:
    try:
        token_data = jwt.decode(
            jwt=token,
            key=Config.JWT_SECRET,
            algorithms=[Config.JWT_ALGORITHM]
        )

        return token_data
    except jwt.PyJWTError as e:
        logging.exception(e)
        return None
