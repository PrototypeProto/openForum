"""
Centralised Redis client.

A single connection pool is shared across the whole application.
Key namespaces replace separate DB numbers:

    blocklist:<jti>       Revoked access/refresh token JTIs
    refresh:<jti>         Active refresh token family  (value = username)
    user:<username>       Cached user role             (value = MemberRoleEnum.value)
    rate:<id>:<route>     Rate limit hit counter       (value = int, TTL = window)

Using namespaced keys in one DB means:
  - One connection pool, not three
  - SCAN patterns work correctly for family revocation
  - Keys are self-describing in redis-cli / monitoring
"""

import redis.asyncio as redis
from src.config import Config
from src.db.enums import MemberRoleEnum

# ---------------------------------------------------------------------------
# Single shared client
# ---------------------------------------------------------------------------

_client: redis.Redis = redis.Redis(
    host=Config.REDIS_HOST,
    port=Config.REDIS_PORT,
    password=Config.REDIS_PASSWORD,
    db=0,
    decode_responses=False,  # we decode manually where needed
)

# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------


def _blocklist_key(jti: str) -> str:
    return f"blocklist:{jti}"


def _refresh_key(jti: str) -> str:
    return f"refresh:{jti}"


def _user_key(username: str) -> str:
    return f"user:{username}"


def _rate_key(identifier: str, route_key: str) -> str:
    """
    Composite rate limit key.
    identifier — IP address (unauthenticated) or username (authenticated)
    route_key  — short stable string identifying the endpoint, e.g. "auth:login"
    """
    return f"rate:{identifier}:{route_key}"


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


async def check_rate_limit(
    identifier: str,
    route_key: str,
    limit: int,
    window_seconds: int,
) -> tuple[int, int]:
    """
    Increment the hit counter for (identifier, route_key) and return
    (current_count, remaining).

    On the first hit within a window the key is created with a TTL of
    window_seconds so Redis cleans it up automatically.

    Raises nothing — the caller decides what to do with the count.
    """
    key = _rate_key(identifier, route_key)
    count = await _client.incr(key)
    if count == 1:
        # First hit in this window — set the expiry
        await _client.expire(key, window_seconds)
    remaining = max(0, limit - count)
    return int(count), remaining


async def get_rate_limit_ttl(identifier: str, route_key: str) -> int:
    """Return seconds until the rate limit window resets, or 0 if no key exists."""
    key = _rate_key(identifier, route_key)
    ttl = await _client.ttl(key)
    return max(0, ttl)


# ---------------------------------------------------------------------------
# JTI blocklist
# ---------------------------------------------------------------------------


async def add_jti_to_blocklist(jti: str, ttl_seconds: int) -> None:
    """
    Blocklist a JTI for exactly as long as the token would still be valid.
    Redis removes the key automatically once the TTL expires, keeping the
    blocklist lean.
    """
    await _client.set(_blocklist_key(jti), "", ex=ttl_seconds)


async def token_in_blocklist(jti: str) -> bool:
    return await _client.get(_blocklist_key(jti)) is not None


# ---------------------------------------------------------------------------
# Refresh token family store
# ---------------------------------------------------------------------------


async def store_refresh_token(jti: str, username: str, ttl_seconds: int) -> None:
    """Record a newly issued refresh token JTI → username mapping."""
    await _client.set(_refresh_key(jti), username, ex=ttl_seconds)


async def get_refresh_token_owner(jti: str) -> str | None:
    """Return the username that owns this refresh JTI, or None if unknown/expired."""
    value = await _client.get(_refresh_key(jti))
    return value.decode() if value is not None else None


async def delete_refresh_token(jti: str) -> None:
    """Remove a refresh JTI from the store (called on rotation)."""
    await _client.delete(_refresh_key(jti))


async def revoke_all_user_refresh_tokens(username: str) -> None:
    """
    Delete every active refresh token belonging to `username`.
    Called on explicit logout and on refresh-token reuse detection.

    Uses SCAN with a pattern so only the refresh namespace is touched —
    no full-keyspace scan.
    """
    pattern = _refresh_key("*")
    cursor = 0
    to_delete: list[str] = []

    while True:
        cursor, keys = await _client.scan(cursor=cursor, match=pattern, count=100)
        for key in keys:
            owner = await _client.get(key)
            if owner and owner.decode() == username:
                to_delete.append(key)
        if cursor == 0:
            break

    if to_delete:
        await _client.delete(*to_delete)


# ---------------------------------------------------------------------------
# User role cache
# ---------------------------------------------------------------------------


async def add_registered_user(username: str, role: MemberRoleEnum) -> None:
    """Cache (or overwrite) a user's role. No expiry — evicted on role change."""
    await _client.set(_user_key(username), role.value)


async def get_user(username: str) -> MemberRoleEnum | None:
    """Return the cached role for `username`, or None on cache miss."""
    raw = await _client.get(_user_key(username))
    if raw is None:
        return None
    try:
        return MemberRoleEnum(raw.decode())
    except ValueError:
        # Corrupted cache entry — evict it so the caller falls through
        # to the DB and backfills a correct value on the next request.
        await _client.delete(_user_key(username))
        return None


async def remove_user(username: str) -> None:
    """Evict a user's role from the cache (e.g. on account deletion)."""
    await _client.delete(_user_key(username))
