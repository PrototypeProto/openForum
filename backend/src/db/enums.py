"""
src/db/enums.py
───────────────
Application-wide enumerations used across models, services, and routes.
"""

from enum import StrEnum


class MemberRoleEnum(StrEnum):
    ADMIN = "admin"
    VIP = "vip"
    USER = "user"


class UserTypeEnum(StrEnum):
    VERIFIED = "verified"
    PENDING = "pending"


class DownloadPermission(StrEnum):
    PUBLIC = "public"  # anyone with the link, no auth required
    SELF = "self"  # uploader only
    PASSWORD = "password"  # anyone with the correct password  # noqa: S105
