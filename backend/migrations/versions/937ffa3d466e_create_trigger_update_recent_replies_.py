"""create trigger: update recent replies/threads

Revision ID: 937ffa3d466e
Revises: e81647b2ac9c
Create Date: 2026-04-04 14:37:35.373365

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '937ffa3d466e'
down_revision: Union[str, Sequence[str], None] = 'e81647b2ac9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
 
    # ------------------------------------------------------------------ #
    #  THREAD: keep last_activity (reply FK) and last_activity_at in sync  #
    #                                                                        #
    #  Fires on reply INSERT, UPDATE (soft-delete), DELETE.                 #
    #                                                                        #
    #  On INSERT:  set last_activity = new reply_id,                        #
    #              last_activity_at  = new created_at                       #
    #                                                                        #
    #  On soft-delete (is_deleted flipped to TRUE):                         #
    #    Find the most recent non-deleted reply and use that instead.        #
    #    If none remain, fall back to the thread's own created_at and        #
    #    set last_activity = NULL.                                           #
    #                                                                        #
    #  Hard DELETE follows the same fallback logic as soft-delete.          #
    # ------------------------------------------------------------------ #
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_thread_last_activity()
        RETURNS TRIGGER AS $$
        DECLARE
            latest_reply RECORD;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE thread
                SET last_activity    = NEW.reply_id,
                    last_activity_at = NEW.created_at
                WHERE thread_id = NEW.thread_id;
 
            ELSIF (TG_OP = 'UPDATE' AND NEW.is_deleted = TRUE AND OLD.is_deleted = FALSE)
               OR TG_OP = 'DELETE' THEN
 
                -- Find the most recent surviving reply for this thread
                SELECT reply_id, created_at
                INTO   latest_reply
                FROM   reply
                WHERE  thread_id  = OLD.thread_id
                  AND  is_deleted = FALSE
                  AND  reply_id  != OLD.reply_id
                ORDER BY created_at DESC
                LIMIT 1;
 
                IF FOUND THEN
                    UPDATE thread
                    SET last_activity    = latest_reply.reply_id,
                        last_activity_at = latest_reply.created_at
                    WHERE thread_id = OLD.thread_id;
                ELSE
                    -- No replies left — reset to thread creation time
                    UPDATE thread
                    SET last_activity    = NULL,
                        last_activity_at = created_at
                    WHERE thread_id = OLD.thread_id;
                END IF;
            END IF;
 
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE TRIGGER trg_thread_last_activity
        AFTER INSERT OR DELETE OR UPDATE OF is_deleted ON reply
        FOR EACH ROW EXECUTE FUNCTION update_thread_last_activity();
        """
    )
 
    # ------------------------------------------------------------------ #
    #  TOPIC: keep last_thread_id and last_activity_at in sync             #
    #                                                                        #
    #  Fires on thread INSERT, UPDATE (soft-delete), DELETE.                #
    #                                                                        #
    #  On INSERT:  if newer than current topic activity, update both.       #
    #                                                                        #
    #  On soft-delete / DELETE:                                             #
    #    If the deleted thread was the topic's last_thread_id, find the     #
    #    next most recent non-deleted thread and use that instead.           #
    #    If none remain, clear both fields.                                 #
    #                                                                        #
    #  Also fires on reply INSERT so topic activity stays fresh when         #
    #  a reply is added to any thread in the topic.                         #
    # ------------------------------------------------------------------ #
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_topic_last_activity_from_thread()
        RETURNS TRIGGER AS $$
        DECLARE
            latest_thread RECORD;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                -- Update topic if this thread is newer than current last activity
                UPDATE topic
                SET last_thread_id   = NEW.thread_id,
                    last_activity_at = NEW.created_at
                WHERE topic_id = NEW.topic_id
                  AND (last_activity_at IS NULL OR NEW.created_at >= last_activity_at);
 
            ELSIF (TG_OP = 'UPDATE' AND NEW.is_deleted = TRUE AND OLD.is_deleted = FALSE)
               OR TG_OP = 'DELETE' THEN
 
                -- Only need to react if this was the topic's most recent thread
                IF EXISTS (
                    SELECT 1 FROM topic
                    WHERE topic_id = OLD.topic_id
                      AND last_thread_id = OLD.thread_id
                ) THEN
                    SELECT thread_id, last_activity_at
                    INTO   latest_thread
                    FROM   thread
                    WHERE  topic_id   = OLD.topic_id
                      AND  is_deleted = FALSE
                      AND  thread_id != OLD.thread_id
                    ORDER BY COALESCE(last_activity_at, created_at) DESC
                    LIMIT 1;
 
                    IF FOUND THEN
                        UPDATE topic
                        SET last_thread_id   = latest_thread.thread_id,
                            last_activity_at = latest_thread.last_activity_at
                        WHERE topic_id = OLD.topic_id;
                    ELSE
                        UPDATE topic
                        SET last_thread_id   = NULL,
                            last_activity_at = NULL
                        WHERE topic_id = OLD.topic_id;
                    END IF;
                END IF;
            END IF;
 
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE TRIGGER trg_topic_last_activity_from_thread
        AFTER INSERT OR DELETE OR UPDATE OF is_deleted ON thread
        FOR EACH ROW EXECUTE FUNCTION update_topic_last_activity_from_thread();
        """
    )
 
    # Topic activity also needs to update when a reply is posted,
    # since a reply in a thread means that topic just had activity.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_topic_last_activity_from_reply()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE topic
                SET last_activity_at = NEW.created_at,
                    last_thread_id   = NEW.thread_id
                WHERE topic_id = (
                    SELECT topic_id FROM thread WHERE thread_id = NEW.thread_id
                )
                AND (last_activity_at IS NULL OR NEW.created_at >= last_activity_at);
            END IF;
 
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE TRIGGER trg_topic_last_activity_from_reply
        AFTER INSERT ON reply
        FOR EACH ROW EXECUTE FUNCTION update_topic_last_activity_from_reply();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_thread_last_activity ON reply;")
    op.execute("DROP FUNCTION IF EXISTS update_thread_last_activity;")
 
    op.execute("DROP TRIGGER IF EXISTS trg_topic_last_activity_from_thread ON thread;")
    op.execute("DROP FUNCTION IF EXISTS update_topic_last_activity_from_thread;")
 
    op.execute("DROP TRIGGER IF EXISTS trg_topic_last_activity_from_reply ON reply;")
    op.execute("DROP FUNCTION IF EXISTS update_topic_last_activity_from_reply;")