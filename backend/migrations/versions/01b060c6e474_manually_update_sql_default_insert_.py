"""manually update SQL default insert behavior

Revision ID: 01b060c6e474
Revises: ce7e24854037
Create Date: 2026-04-01 21:41:43.707964

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "01b060c6e474"
down_revision: Union[str, Sequence[str], None] = "ce7e24854037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # UUIDs
    op.alter_column("user_id", "id", server_default=sa.func.gen_random_uuid())
    op.alter_column("topic", "topic_id", server_default=sa.func.gen_random_uuid())
    op.alter_column("topic_group", "group_id", server_default=sa.func.gen_random_uuid())
    op.alter_column("thread", "thread_id", server_default=sa.func.gen_random_uuid())
    op.alter_column("reply", "reply_id", server_default=sa.func.gen_random_uuid())

    # Timestamps
    op.alter_column("topic", "created_at", server_default=sa.func.now())
    op.alter_column("thread", "created_at", server_default=sa.func.now())
    op.alter_column("reply", "created_at", server_default=sa.func.now())

    # Dates
    op.alter_column("pending_user", "join_date", server_default=sa.func.current_date())
    op.alter_column("user", "verified_date", server_default=sa.func.current_date())
    op.alter_column("user", "last_login_date", server_default=sa.func.current_date())

    # Integers
    op.alter_column("topic", "display_order", server_default="0")
    op.alter_column("topic", "thread_count", server_default="0")
    op.alter_column("topic", "reply_count", server_default="0")
    op.alter_column("topic_group", "display_order", server_default="0")
    op.alter_column("thread", "reply_count", server_default="0")
    op.alter_column("thread", "upvote_count", server_default="0")
    op.alter_column("thread", "downvote_count", server_default="0")
    op.alter_column("thread", "view_count", server_default="0")
    op.alter_column("reply", "upvote_count", server_default="0")
    op.alter_column("reply", "downvote_count", server_default="0")

    # Booleans
    op.alter_column("topic", "is_locked", server_default="false")
    op.alter_column("thread", "is_pinned", server_default="false")
    op.alter_column("thread", "is_locked", server_default="false")
    op.alter_column("thread", "is_deleted", server_default="false")
    op.alter_column("reply", "is_deleted", server_default="false")

    # Enum
    op.alter_column("user", "role", server_default="user")


def downgrade() -> None:
    op.alter_column("user_id", "id", server_default=None)
    op.alter_column("topic", "topic_id", server_default=None)
    op.alter_column("topic_group", "group_id", server_default=None)
    op.alter_column("thread", "thread_id", server_default=None)
    op.alter_column("reply", "reply_id", server_default=None)
    op.alter_column("topic", "created_at", server_default=None)
    op.alter_column("thread", "created_at", server_default=None)
    op.alter_column("reply", "created_at", server_default=None)
    op.alter_column("pending_user", "join_date", server_default=None)
    op.alter_column("user", "verified_date", server_default=None)
    op.alter_column("user", "last_login_date", server_default=None)
    op.alter_column("topic", "display_order", server_default=None)
    op.alter_column("topic", "thread_count", server_default=None)
    op.alter_column("topic", "reply_count", server_default=None)
    op.alter_column("topic_group", "display_order", server_default=None)
    op.alter_column("thread", "reply_count", server_default=None)
    op.alter_column("thread", "upvote_count", server_default=None)
    op.alter_column("thread", "downvote_count", server_default=None)
    op.alter_column("thread", "view_count", server_default=None)
    op.alter_column("reply", "upvote_count", server_default=None)
    op.alter_column("reply", "downvote_count", server_default=None)
    op.alter_column("topic", "is_locked", server_default=None)
    op.alter_column("thread", "is_pinned", server_default=None)
    op.alter_column("thread", "is_locked", server_default=None)
    op.alter_column("thread", "is_deleted", server_default=None)
    op.alter_column("reply", "is_deleted", server_default=None)
    op.alter_column("user", "role", server_default=None)
