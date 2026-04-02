"""update trigger: update_thread_vote_counts()

Revision ID: e81647b2ac9c
Revises: 01b060c6e474
Create Date: 2026-04-01 22:40:28.294148

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e81647b2ac9c'
down_revision: Union[str, Sequence[str], None] = '01b060c6e474'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
        # vote count
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_thread_vote_counts()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.is_upvote THEN
                    UPDATE thread SET upvote_count = upvote_count + 1 WHERE thread_id = NEW.thread_id;
                ELSE
                    UPDATE thread SET downvote_count = downvote_count + 1 WHERE thread_id = NEW.thread_id;
                END IF;
            ELSIF TG_OP = 'UPDATE' THEN
                IF NEW.is_upvote THEN
                    UPDATE thread SET upvote_count = upvote_count + 1 WHERE thread_id = NEW.thread_id;
                    UPDATE thread SET downvote_count = downvote_count - 1 WHERE thread_id = NEW.thread_id;
                ELSE
                    UPDATE thread SET downvote_count = downvote_count + 1 WHERE thread_id = NEW.thread_id;
                    UPDATE thread SET upvote_count = upvote_count - 1 WHERE thread_id = NEW.thread_id;
                END IF;
            ELSIF TG_OP = 'DELETE' THEN
                IF OLD.is_upvote THEN
                    UPDATE thread SET upvote_count = upvote_count - 1 WHERE thread_id = OLD.thread_id;
                ELSE
                    UPDATE thread SET downvote_count = downvote_count - 1 WHERE thread_id = OLD.thread_id;
                END IF;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """
    )
    op.execute(
        """
        CREATE OR REPLACE TRIGGER trg_thread_vote_counts
        AFTER INSERT OR DELETE OR UPDATE ON thread_vote
        FOR EACH ROW EXECUTE FUNCTION update_thread_vote_counts();
    """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_reply_vote_counts()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.is_upvote THEN
                    UPDATE reply SET upvote_count = upvote_count + 1 WHERE reply_id = NEW.reply_id;
                ELSE
                    UPDATE reply SET downvote_count = downvote_count + 1 WHERE reply_id = NEW.reply_id;
                END IF;
            ELSIF TG_OP = 'UPDATE' THEN
                IF NEW.is_upvote THEN
                    UPDATE reply SET upvote_count = upvote_count + 1 WHERE reply_id = NEW.reply_id;
                    UPDATE reply SET downvote_count = downvote_count - 1 WHERE reply_id = NEW.reply_id;
                ELSE
                    UPDATE reply SET downvote_count = downvote_count + 1 WHERE reply_id = NEW.reply_id;
                    UPDATE reply SET upvote_count = upvote_count - 1 WHERE reply_id = NEW.reply_id;
                END IF;
            ELSIF TG_OP = 'DELETE' THEN
                IF OLD.is_upvote THEN
                    UPDATE reply SET upvote_count = upvote_count - 1 WHERE reply_id = OLD.reply_id;
                ELSE
                    UPDATE reply SET downvote_count = downvote_count - 1 WHERE reply_id = OLD.reply_id;
                END IF;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """
    )
    op.execute(
        """
        CREATE OR REPLACE TRIGGER trg_reply_vote_counts
        AFTER INSERT OR DELETE OR UPDATE ON reply_vote
        FOR EACH ROW EXECUTE FUNCTION update_reply_vote_counts();
    """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_thread_vote_counts ON thread_vote;")
    op.execute("DROP FUNCTION IF EXISTS update_thread_vote_counts;")

    op.execute("DROP TRIGGER IF EXISTS trg_reply_vote_counts ON reply_vote;")
    op.execute("DROP FUNCTION IF EXISTS update_reply_vote_counts;")