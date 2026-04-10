"""
src/exceptions.py
─────────────────
Typed application exceptions.

All exceptions inherit from AppException which carries an HTTP status code
and a detail message. The global handler in src/__init__.py converts them
to consistent JSON responses.

Usage in service layer:
    raise NotFoundError("Thread not found")
    raise ForbiddenError("Topic is locked")

Usage in routes:
    Nothing — exceptions propagate up and the global handler catches them.
    Routes no longer need try/except blocks for expected error conditions.

The consistent response shape for all AppExceptions is:
    {"error": "<code>", "detail": "<message>"}
"""

from fastapi import status


class AppException(Exception):
    """
    Base class for all application exceptions.
    Carries an HTTP status code and a user-facing detail message.
    """
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.__class__.__doc__ or "An unexpected error occurred"
        super().__init__(self.detail)


# ---------------------------------------------------------------------------
# 400 Bad Request
# ---------------------------------------------------------------------------

class BadRequestError(AppException):
    """Bad request."""
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"


class InvalidPasswordError(BadRequestError):
    """A password is required or the provided password is incorrect."""
    code = "invalid_password"


class FileTooLargeError(BadRequestError):
    """File exceeds the maximum allowed size."""
    code = "file_too_large"


class QuotaExceededError(BadRequestError):
    """Upload would exceed storage quota."""
    code = "quota_exceeded"


class InvalidParentReplyError(BadRequestError):
    """Parent reply does not belong to this thread."""
    code = "invalid_parent_reply"


class UnsupportedFileTypeError(BadRequestError):
    """File type is not supported."""
    code = "unsupported_file_type"


class InvalidPathError(BadRequestError):
    """File path is invalid."""
    code = "invalid_path"


# ---------------------------------------------------------------------------
# 401 Unauthorized — identity could not be verified / session expired
# ---------------------------------------------------------------------------

class UnauthorizedError(AppException):
    """Authentication required or session has expired."""
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class TokenExpiredError(UnauthorizedError):
    """Token has expired."""
    code = "token_expired"


class SessionRevokedError(UnauthorizedError):
    """Session was revoked. Please log in again."""
    code = "session_revoked"


class RoleChangedError(UnauthorizedError):
    """Session invalidated due to role change. Please log in again."""
    code = "role_changed"


class RefreshTokenReuseError(UnauthorizedError):
    """Refresh token reuse detected. All sessions revoked."""
    code = "refresh_token_reuse"


# ---------------------------------------------------------------------------
# 403 Forbidden — identity is known but access is denied
# ---------------------------------------------------------------------------

class ForbiddenError(AppException):
    """You do not have permission to perform this action."""
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class LockedError(ForbiddenError):
    """This resource is locked and cannot be modified."""
    code = "locked"


class InsufficientPermissionsError(ForbiddenError):
    """Insufficient permissions."""
    code = "insufficient_permissions"


class InvalidCredentialsError(ForbiddenError):
    """Invalid username and/or password."""
    code = "invalid_credentials"


# ---------------------------------------------------------------------------
# 404 Not Found
# ---------------------------------------------------------------------------

class NotFoundError(AppException):
    """The requested resource was not found."""
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class FileNotFoundError(NotFoundError):
    """File not found."""
    code = "file_not_found"


# ---------------------------------------------------------------------------
# 409 Conflict
# ---------------------------------------------------------------------------

class ConflictError(AppException):
    """A conflict occurred with the current state of the resource."""
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class AlreadyExistsError(ConflictError):
    """A resource with this identifier already exists."""
    code = "already_exists"


class AlreadyVerifiedError(ConflictError):
    """User is already verified."""
    code = "already_verified"


# ---------------------------------------------------------------------------
# 500 Internal Server Error
# ---------------------------------------------------------------------------

class InternalError(AppException):
    """An internal server error occurred."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "internal_error"
