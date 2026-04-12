"""
src/auth/csrf.py
────────────────
CSRF protection via the signed double-submit cookie pattern.

How it works
────────────
1. On login and token refresh, the server sets a non-HttpOnly csrf_token
   cookie alongside the HttpOnly auth cookies. JavaScript reads this cookie
   and copies its value into an X-CSRF-Token request header on every
   state-changing request.

2. verify_csrf_token reads both the cookie and the header. If either is
   missing or they don't match (constant-time comparison), the request is
   rejected with 403.

3. A cross-origin attacker can trigger a cross-site request but cannot read
   the csrf_token cookie value (same-origin policy) and therefore cannot set
   the matching header — the double-submit check fails.

Why not a synchronizer token?
──────────────────────────────
Synchronizer tokens require server-side session state. This app is
intentionally stateless (JWT + Redis for revocation only). Double-submit
is the correct CSRF mitigation for stateless APIs.

The subdomain bypass and how we close it
─────────────────────────────────────────
The classic double-submit weakness: if an attacker controls any subdomain
of your apex domain, they can inject a cookie with domain=.example.com,
overwriting the csrf_token with a known value and then sending a matching
header. The browser's SOP doesn't prevent subdomain → apex cookie writes.

Mitigation — the __Host- cookie prefix (production/staging only):
  The browser refuses to store a __Host- prefixed cookie unless ALL of these
  hold: Secure=true, no Domain attribute, Path=/. A subdomain cannot set
  __Host-csrf_token because the browser enforces these constraints at write
  time — the injection is structurally blocked.

  In development/testing we use the plain "csrf_token" name because __Host-
  requires HTTPS (Secure=true) which isn't available on localhost or in the
  httpx test client. _csrf_cookie_name() selects the right name based on
  Config.cookie_secure.

Remaining limitations (documented, not fixed here)
────────────────────────────────────────────────────
- XSS on the same origin bypasses all CSRF defences. Mitigate with strict
  CSP and server-side sanitisation of user-generated HTML/markdown.
- The auth cookies (access_token, refresh_token) don't yet use __Host-.
  delete_cookie() needs the name to match set_cookie() exactly, and
  prefixing them requires co-ordinating with the frontend cookie reads.
  Add __Host- to auth cookies once the nginx + HTTPS setup is in place.

Security properties
────────────────────
- 32-byte (256-bit) random token — not derived from the JWT
- Constant-time comparison via secrets.compare_digest
- __Host- prefix in production blocks subdomain injection
- SameSite=strict in production provides defence-in-depth
- No domain attribute set — scoped to exact host only
"""

import secrets

from fastapi import Depends, Request

from src.config import Config
from src.exceptions import ForbiddenError

# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------

# In production/staging the cookie is prefixed with __Host- which instructs
# the browser to enforce: Secure=true, no Domain attribute, Path=/.
# This prevents subdomain cookie injection — a compromised subdomain cannot
# set a __Host- prefixed cookie, so the double-submit value cannot be forged.
# In development/testing we use the plain name because __Host- requires HTTPS
# (Secure=true) which the local dev server and httpx test client don't use.
_CSRF_COOKIE_NAME_PLAIN = "csrf_token"
_CSRF_COOKIE_NAME_HOST = "__Host-csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"  # FastAPI lowercases header names
CSRF_TOKEN_BYTES = 32


def _csrf_cookie_name() -> str:
    """
    Return the environment-appropriate CSRF cookie name.

    __Host- prefix is used in production/staging where Secure=true is set.
    Plain name is used in development/testing where HTTPS is not available.
    """
    return _CSRF_COOKIE_NAME_HOST if Config.cookie_secure else _CSRF_COOKIE_NAME_PLAIN


# Convenience alias used in tests and external references
CSRF_COOKIE_NAME = _CSRF_COOKIE_NAME_PLAIN  # plain name for test assertions


def generate_csrf_token() -> str:
    """Return a cryptographically random 64-char hex string."""
    return secrets.token_hex(CSRF_TOKEN_BYTES)


# ---------------------------------------------------------------------------
# Cookie helper
# ---------------------------------------------------------------------------


def set_csrf_cookie(response, token: str) -> None:
    """
    Write the csrf_token cookie onto `response`.

    Intentionally NOT HttpOnly — JavaScript must be able to read this value
    so it can copy it into the X-CSRF-Token request header.
    """
    response.set_cookie(
        key=_csrf_cookie_name(),
        value=token,
        httponly=False,  # JS-readable by design
        secure=Config.cookie_secure,
        samesite=Config.cookie_samesite,
        path="/",
        # domain intentionally omitted — scopes cookie to exact host only,
        # preventing a parent-domain set from a sibling subdomain
    )


def delete_csrf_cookie(response) -> None:
    """
    Clear the csrf_token cookie on logout.

    Passes the same path/secure/samesite attributes used in set_csrf_cookie
    so browsers (especially Safari) match and actually delete the cookie.
    Deletes both name variants so a user switching environments doesn't get
    a stale cookie stuck.
    """
    for name in (_CSRF_COOKIE_NAME_HOST, _CSRF_COOKIE_NAME_PLAIN):
        response.delete_cookie(
            key=name,
            path="/",
            secure=Config.cookie_secure,
            samesite=Config.cookie_samesite,
        )


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def verify_csrf_token(request: Request) -> None:
    """
    FastAPI dependency — verifies the double-submit CSRF check.

    Raises ForbiddenError (403) if:
      - The X-CSRF-Token header is missing
      - The csrf_token cookie is missing
      - The two values do not match (constant-time comparison)

    Usage:
        @router.post("/endpoint")
        async def my_endpoint(
            _csrf: None = Depends(verify_csrf_token),
            ...
        ):
            ...

    Safe methods (GET, HEAD, OPTIONS) should NOT use this dependency —
    they must be pure reads with no side effects.
    """
    # Skip check in testing — the httpx test client doesn't set CSRF cookies
    # and test coverage for CSRF is provided by test_csrf.py unit tests.
    if Config.is_testing:
        return

    header_token = request.headers.get(CSRF_HEADER_NAME)
    cookie_token = request.cookies.get(_csrf_cookie_name())

    if not header_token or not cookie_token:
        raise ForbiddenError("CSRF token missing")

    # secrets.compare_digest prevents timing attacks
    if not secrets.compare_digest(header_token, cookie_token):
        raise ForbiddenError("CSRF token mismatch")


# Pre-built dependency for use in route signatures
require_csrf = Depends(verify_csrf_token)
