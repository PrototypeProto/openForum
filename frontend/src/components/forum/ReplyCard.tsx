import type { ReplyRead } from "../../types/forumTypes";
import "./ReplyCard.css";

interface ReplyCardProps {
  reply: ReplyRead
  isOP: boolean
  currentUserId: string | null
  parentReply: ReplyRead | null
  editingReplyId: string | null
  editBody: string
  onSetEditBody: (v: string) => void
  onStartEdit: (r: ReplyRead) => void
  onCancelEdit: () => void
  onSubmitEdit: (replyId: string) => void
  onReplyTo: (r: ReplyRead) => void
  onDelete: (replyId: string) => void
  onVote: (replyId: string, isUpvote: boolean) => void
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ReplyCard({
  reply,
  isOP,
  currentUserId,
  parentReply,
  editingReplyId,
  editBody,
  onSetEditBody,
  onStartEdit,
  onCancelEdit,
  onSubmitEdit,
  onReplyTo,
  onDelete,
  onVote,
}: ReplyCardProps) {
  const isEditing = editingReplyId === reply.reply_id;
  const isOwn = currentUserId === reply.author_id;

  // Resolve the parent for the "replying to" banner.
  // Parent is either on the same page (in the replies list) or fetched into parentCache.
  const showParentBanner = reply.parent_reply_id !== null && parentReply !== null;

  return (
    <div className={`reply-card${isOP ? " reply-card--op" : ""}${reply.is_deleted ? " reply-card--deleted" : ""}`}>

      {/* Section 1: commenter */}
      <div className="reply-card-author">
        <div className="reply-avatar-placeholder" />
        <span className="reply-author-username">{reply.author_username}</span>
        {isOP && <span className="reply-op-badge">OP</span>}
      </div>

      {/* Section 2: content */}
      <div className="reply-card-content">

        {/* Top row: created_at left, reply number right */}
        <div className="reply-card-meta">
          <span className="reply-created-at">
            {formatDate(reply.created_at)}
            {reply.updated_at && <span className="reply-edited-flag"> (edited)</span>}
          </span>
          <span className="reply-number">#{reply.reply_number}</span>
        </div>

        {/* Parent banner */}
        {showParentBanner && !reply.is_deleted && (
          <div className="reply-parent-banner">
            <span className="reply-parent-label">↩ replying to {parentReply!.author_username}</span>
            <p className="reply-parent-body">
              {parentReply!.is_deleted ? "[deleted]" : parentReply!.body.slice(0, 120) + (parentReply!.body.length > 120 ? "…" : "")}
            </p>
          </div>
        )}

        {/* Body or edit form */}
        {isEditing ? (
          <div className="reply-edit-form">
            <textarea
              className="reply-edit-textarea"
              value={editBody}
              onChange={(e) => onSetEditBody(e.target.value)}
              rows={4}
            />
            <div className="reply-edit-actions">
              <button className="reply-btn reply-btn--primary" onClick={() => onSubmitEdit(reply.reply_id)}>
                Save
              </button>
              <button className="reply-btn reply-btn--ghost" onClick={onCancelEdit}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <p className="reply-body">
            {reply.is_deleted ? <em className="reply-deleted-text">[deleted]</em> : reply.body}
          </p>
        )}

        {/* Bottom row: votes + actions */}
        {!reply.is_deleted && !isEditing && (
          <div className="reply-card-actions">
            <div className="reply-vote-group">
              <button
                className={`reply-vote-btn${reply.upvote_count > reply.downvote_count ? " reply-vote-btn--up-active" : ""}`}
                aria-label="upvote"
                onClick={() => onVote(reply.reply_id, true)}
              >▲</button>
              <span className="reply-vote-count">{reply.upvote_count - reply.downvote_count}</span>
              <button
                className={`reply-vote-btn${reply.downvote_count > reply.upvote_count ? " reply-vote-btn--down-active" : ""}`}
                aria-label="downvote"
                onClick={() => onVote(reply.reply_id, false)}
              >▼</button>
            </div>
            <div className="reply-card-action-right">
              {isOwn && (
                <>
                  <button className="reply-btn reply-btn--ghost" onClick={() => onStartEdit(reply)}>
                    Edit
                  </button>
                  <button className="reply-btn reply-btn--danger" onClick={() => onDelete(reply.reply_id)}>
                    Delete
                  </button>
                </>
              )}
              <button className="reply-btn reply-btn--ghost" onClick={() => onReplyTo(reply)}>
                Reply
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}