"""
tests/test_utils.py
───────────────────
Pure unit tests for src/auth/utils.py.
No I/O, no DB, no Redis — these run in microseconds.
"""

import time
import pytest
from datetime import datetime, timezone, timedelta
from uuid import UUID

from src.auth.utils import (
    generate_passwd_hash,
    verify_passwd,
    create_access_token,
    decode_token,
    seconds_until_expiry,
    ACCESS_TOKEN_EXPIRY_SECONDS,
    REFRESH_TOKEN_EXPIRY_SECONDS,
)


# ── Password hashing ──────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        assert generate_passwd_hash("secret") != "secret"

    def test_correct_password_verifies(self):
        hashed = generate_passwd_hash("correct")
        assert verify_passwd("correct", hashed) is True

    def test_wrong_password_fails(self):
        hashed = generate_passwd_hash("correct")
        assert verify_passwd("wrong", hashed) is False

    def test_empty_password_hashes_and_verifies(self):
        hashed = generate_passwd_hash("")
        assert verify_passwd("", hashed) is True

    def test_two_hashes_of_same_password_differ(self):
        # bcrypt uses a random salt each time
        h1 = generate_passwd_hash("same")
        h2 = generate_passwd_hash("same")
        assert h1 != h2


# ── Token creation & decoding ─────────────────────────────────────────────────

USER_DATA = {"user_id": "abc-123", "username": "testuser", "nickname": None}


class TestCreateAccessToken:
    def test_returns_string(self):
        token = create_access_token(user_data=USER_DATA)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decoded_payload_matches_input(self):
        token = create_access_token(user_data=USER_DATA)
        data = decode_token(token)
        assert data["user"]["username"] == "testuser"
        assert data["user"]["user_id"] == "abc-123"

    def test_access_token_has_refresh_false(self):
        token = create_access_token(user_data=USER_DATA)
        data = decode_token(token)
        assert data["refresh"] is False

    def test_refresh_token_has_refresh_true(self):
        token = create_access_token(user_data=USER_DATA, refresh=True)
        data = decode_token(token)
        assert data["refresh"] is True

    def test_token_has_jti(self):
        token = create_access_token(user_data=USER_DATA)
        data = decode_token(token)
        # JTI should be a valid UUID string
        UUID(data["jti"])

    def test_two_tokens_have_different_jtis(self):
        t1 = create_access_token(user_data=USER_DATA)
        t2 = create_access_token(user_data=USER_DATA)
        assert decode_token(t1)["jti"] != decode_token(t2)["jti"]

    def test_token_has_iat(self):
        before = int(datetime.now(timezone.utc).timestamp())
        token = create_access_token(user_data=USER_DATA)
        after = int(datetime.now(timezone.utc).timestamp())
        iat = decode_token(token)["iat"]
        assert before <= iat <= after

    def test_custom_expiry_respected(self):
        token = create_access_token(user_data=USER_DATA, expiry_seconds=120)
        data = decode_token(token)
        now = int(datetime.now(timezone.utc).timestamp())
        # exp should be approximately now + 120s (allow 5s drift)
        assert abs(data["exp"] - (now + 120)) < 5

    def test_default_access_expiry(self):
        token = create_access_token(user_data=USER_DATA)
        data = decode_token(token)
        now = int(datetime.now(timezone.utc).timestamp())
        assert abs(data["exp"] - (now + ACCESS_TOKEN_EXPIRY_SECONDS)) < 5

    def test_role_not_in_payload(self):
        token = create_access_token(user_data=USER_DATA)
        data = decode_token(token)
        assert "role" not in data["user"]


class TestDecodeToken:
    def test_returns_none_for_garbage(self):
        assert decode_token("not.a.token") is None

    def test_raises_for_expired_token(self):
        token = create_access_token(user_data=USER_DATA, expiry_seconds=-1)
        with pytest.raises(Exception, match="expired"):
            decode_token(token)

    def test_tampered_signature_returns_none(self):
        token = create_access_token(user_data=USER_DATA)
        # Flip the last character of the signature
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        assert decode_token(tampered) is None


# ── seconds_until_expiry ──────────────────────────────────────────────────────

class TestSecondsUntilExpiry:
    def test_future_token_returns_positive(self):
        token = create_access_token(user_data=USER_DATA, expiry_seconds=300)
        data = decode_token(token)
        remaining = seconds_until_expiry(data)
        assert 295 <= remaining <= 300

    def test_expired_token_returns_zero(self):
        # Manually craft a payload with exp in the past
        past_exp = int((datetime.now(timezone.utc) - timedelta(seconds=100)).timestamp())
        token_data = {"exp": past_exp}
        assert seconds_until_expiry(token_data) == 0

    def test_missing_exp_returns_zero(self):
        assert seconds_until_expiry({}) == 0

    def test_access_token_expiry_is_75_minutes(self):
        # Guard against accidentally changing the constant
        assert ACCESS_TOKEN_EXPIRY_SECONDS == 60 * 75

    def test_refresh_token_expiry_is_1_week(self):
        assert REFRESH_TOKEN_EXPIRY_SECONDS == 60 * 60 * 24 * 7
