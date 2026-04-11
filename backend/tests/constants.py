"""
tests/constants.py
──────────────────
Centralised constants for the test suite.

Keeping magic strings here means:
  - bandit / ruff S106/S107 suppressions live in one place, not scattered
    across every test file
  - changing a password policy (e.g. raising PASSWORD_MIN_LEN) only
    requires updating this file
  - readers can see at a glance that these are test-only values, not
    leaked production secrets

Naming convention:
  TEST_PASSWORD_*   — passwords passed to make_user / register_user
  TEST_FILE_PW_*    — passwords used for TempFS password-protected files
  TEST_SIGNUP_*     — payloads sent directly to the /auth/signup endpoint
                       (must satisfy RegisterUserModel validators)
  TEST_BODY_*       — generic placeholder body/content strings used where
                       the value doesn't affect the assertion
"""

# ---------------------------------------------------------------------------
# User passwords
#
# TEST_PASSWORD       — default for make_user() and most service-layer tests;
#                       long enough to satisfy PASSWORD_MIN_LEN (12)
# TEST_PASSWORD_ALT   — used where two distinct passwords are needed in one
#                       test (e.g. correct vs wrong credential checks)
# TEST_PASSWORD_WRONG — deliberately incorrect password for negative tests
# TEST_PASSWORD_STUB  — bare-minimum placeholder when the value is irrelevant
#                       (e.g. inserting a PendingUser row where only the hash
#                       matters, not the original plaintext)
# ---------------------------------------------------------------------------

TEST_PASSWORD = "testpassword1"  # noqa: S105
TEST_PASSWORD_ALT = "alternatepass1"  # noqa: S105
TEST_PASSWORD_WRONG = "wrongpassword1"  # noqa: S105
TEST_PASSWORD_STUB = "stubpassword1"  # noqa: S105

# ---------------------------------------------------------------------------
# Signup-endpoint passwords
#
# These are sent as JSON to POST /auth/signup and must satisfy
# RegisterUserModel's PASSWORD_MIN_LEN (12) / PASSWORD_MAX_LEN (128)
# validators. Keep them at exactly 12 characters to stay minimal.
# ---------------------------------------------------------------------------

TEST_SIGNUP_PASSWORD = "signuppass12"  # noqa: S105
TEST_SIGNUP_PASSWORD_DUPE = "dupepassword"  # noqa: S105

# ---------------------------------------------------------------------------
# TempFS file passwords
#
# Used when creating password-protected TempFile records.
# TEST_FILE_PW         — correct password (hash stored in DB, plaintext supplied on download)
# TEST_FILE_PW_WRONG   — wrong password for negative access tests
# ---------------------------------------------------------------------------

TEST_FILE_PW = "filepassword1"  # noqa: S105
TEST_FILE_PW_WRONG = "wrongfilepass"  # noqa: S105

# ---------------------------------------------------------------------------
# Generic body / content placeholders
#
# Used for thread body, reply body, or any other string field where
# the exact value is irrelevant to the assertion being made.
# ---------------------------------------------------------------------------

TEST_BODY = "Test body content."
TEST_REPLY_BODY = "Test reply content."
TEST_TITLE = "Test Thread Title"

# ---------------------------------------------------------------------------
# Named content for assertion-specific tests
#
# These differ from TEST_BODY/TEST_TITLE in that the test actually asserts
# on the returned value (e.g. "Updated Title" must appear in the response).
# Using a constant makes it obvious the value is intentional and allows
# a single change if the assertion needs updating.
# ---------------------------------------------------------------------------

TEST_TITLE_CREATE = "My New Thread"  # used in create_thread happy-path
TEST_TITLE_UPDATED = "Updated Title"  # used in update_thread assertion
TEST_BODY_UPDATED = "Updated body"  # paired with TEST_TITLE_UPDATED
TEST_BODY_EDIT = "Edited reply content."  # used in update_reply assertion
TEST_REPLY_BODY_CREATE = "Great thread!"  # create_reply happy-path body

# ---------------------------------------------------------------------------
# Trigger test content
#
# Thread/reply data used inside @pytest.mark.triggers tests. Kept separate
# so they read clearly as "this is the real-commit trigger test dataset".
# ---------------------------------------------------------------------------

TEST_TRIGGER_TITLE_1 = "T1"
TEST_TRIGGER_TITLE_2 = "T2"
TEST_TRIGGER_REPLY_BODY = "reply 1"
