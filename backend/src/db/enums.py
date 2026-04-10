"""
src/db/enums.py
───────────────
Application-wide enumerations used across models, services, and routes.
"""
from enum import Enum


class MemberRoleEnum(str, Enum):
    ADMIN = "admin"
    VIP = "vip"
    USER = "user"


class UserTypeEnum(str, Enum):
    VERIFIED = "verified"
    PENDING = "pending"


class DownloadPermission(str, Enum):
    PUBLIC = "public"       # anyone with the link, no auth required
    SELF = "self"           # uploader only
    PASSWORD = "password"   # anyone with the correct password