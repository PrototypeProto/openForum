"""Create triggers for forum-related tables

Revision ID: dbf6e01bd472
Revises: 58fac84c1e22
Create Date: 2026-03-30 15:58:29.494927

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'dbf6e01bd472'
down_revision: Union[str, Sequence[str], None] = '58fac84c1e22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # thread count
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_topic_thread_count()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE topic SET thread_count = thread_count + 1 WHERE topic_id = NEW.topic_id;
            ELSIF TG_OP = 'DELETE' THEN
                UPDATE topic SET thread_count = thread_count - 1 WHERE topic_id = OLD.topic_id;
            ELSIF TG_OP = 'UPDATE' AND NEW.is_deleted = TRUE AND OLD.is_deleted = FALSE THEN
                UPDATE topic SET thread_count = thread_count - 1 WHERE topic_id = OLD.topic_id;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """
    )
    op.execute(
        """
        CREATE OR REPLACE TRIGGER trg_topic_thread_count
        AFTER INSERT OR DELETE OR UPDATE OF is_deleted ON thread
        FOR EACH ROW EXECUTE FUNCTION update_topic_thread_count();
    """
    )

    # reply count
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_reply_counts()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE thread SET reply_count = reply_count + 1 WHERE thread_id = NEW.thread_id;
                UPDATE topic SET reply_count = reply_count + 1
                    WHERE topic_id = (SELECT topic_id FROM thread WHERE thread_id = NEW.thread_id);
            ELSIF TG_OP = 'DELETE' THEN
                UPDATE thread SET reply_count = reply_count - 1 WHERE thread_id = OLD.thread_id;
                UPDATE topic SET reply_count = reply_count - 1
                    WHERE topic_id = (SELECT topic_id FROM thread WHERE thread_id = OLD.thread_id);
            ELSIF TG_OP = 'UPDATE' AND NEW.is_deleted = TRUE AND OLD.is_deleted = FALSE THEN
                UPDATE thread SET reply_count = reply_count - 1 WHERE thread_id = OLD.thread_id;
                UPDATE topic SET reply_count = reply_count - 1
                    WHERE topic_id = (SELECT topic_id FROM thread WHERE thread_id = OLD.thread_id);
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """
    )
    op.execute(
        """
        CREATE OR REPLACE TRIGGER trg_reply_counts
        AFTER INSERT OR DELETE OR UPDATE OF is_deleted ON reply
        FOR EACH ROW EXECUTE FUNCTION update_reply_counts();
    """
    )

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
        AFTER INSERT OR DELETE ON thread_vote
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
        AFTER INSERT OR DELETE ON reply_vote
        FOR EACH ROW EXECUTE FUNCTION update_reply_vote_counts();
    """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_topic_thread_count ON thread;")
    op.execute("DROP FUNCTION IF EXISTS update_topic_thread_count;")

    op.execute("DROP TRIGGER IF EXISTS trg_reply_counts ON reply;")
    op.execute("DROP FUNCTION IF EXISTS update_reply_counts;")

    op.execute("DROP TRIGGER IF EXISTS trg_thread_vote_counts ON thread_vote;")
    op.execute("DROP FUNCTION IF EXISTS update_thread_vote_counts;")

    op.execute("DROP TRIGGER IF EXISTS trg_reply_vote_counts ON reply_vote;")
    op.execute("DROP FUNCTION IF EXISTS update_reply_vote_counts;")
