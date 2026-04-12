-- Step 1: generate a UUID for the admin account
-- Step 2: insert into user_id (the FK source table)
-- Step 3: insert into "user" (the verified user table)

-- Run this in psql or your DB client.
-- Replace <BCRYPT_HASH> with the output of:
--   python3 -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('your_password'))"

BEGIN;

-- Reserve the ID
WITH new_id AS (
    INSERT INTO user_id DEFAULT VALUES
    RETURNING id
)
INSERT INTO "user" (
    user_id,
    username,
    email,
    password_hash,
    nickname,
    join_date,
    verified_date,
    last_login_date,
    role
)
SELECT
    id,
    'jj',                -- change to admin
    NULL,                   -- email (optional)
    '$2b$12$.UqmfbUHxGf3h4vPicXO/uhLHXx1SdcWUNdmCngrYgwXiAUMSiDSe',        -- paste your hash here
    NULL,                   -- nickname (optional)
    CURRENT_DATE,
    CURRENT_DATE,
    NULL,
    'admin'
FROM new_id;

COMMIT;
