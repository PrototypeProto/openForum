import type { ReplyRead } from "../../types/forumTypes";
import "./ReplyBox.css";

interface ReplyBoxProps {
  body: string
  onBodyChange: (v: string) => void
  replyingTo: ReplyRead | null
  onClearReplyingTo: () => void
  onSubmit: () => void
  isLocked: boolean
  submitError: string | null
}

export default function ReplyBox({
  body,
  onBodyChange,
  replyingTo,
  onClearReplyingTo,
  onSubmit,
  isLocked,
  submitError,
}: ReplyBoxProps) {
  if (isLocked) {
    return (
      <div className="reply-box reply-box--locked">
        <span>This thread is locked. No new replies can be posted.</span>
      </div>
    );
  }

  return (
    <div className="reply-box">
      {replyingTo && (
        <div className="reply-box-banner">
          <span>↩ replying to <strong>{replyingTo.author_username}</strong></span>
          <button
            className="reply-box-clear-btn"
            onClick={onClearReplyingTo}
            aria-label="Cancel reply"
          >
            ✕
          </button>
        </div>
      )}

      <textarea
        className="reply-box-textarea"
        placeholder="Write a reply…"
        value={body}
        onChange={(e) => onBodyChange(e.target.value)}
        rows={5}
      />

      {submitError && <p className="reply-box-error">{submitError}</p>}

      <div className="reply-box-footer">
        <button
          className="reply-box-submit"
          onClick={onSubmit}
          disabled={!body.trim()}
        >
          Post Reply
        </button>
      </div>
    </div>
  );
}