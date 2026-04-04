import { useNavigate } from "react-router-dom";
import type { ThreadListItem } from "../../types/forumTypes";
import "./ThreadCard.css";

function formatActivity(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const now = new Date();
  const diff = Math.floor((now.getTime() - d.getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString();
}

interface ThreadCardProps {
  thread: ThreadListItem;
}

export default function ThreadCard({ thread }: ThreadCardProps) {
  const navigate = useNavigate();
  const netVotes = thread.upvote_count - thread.downvote_count;



  return (
    <div
      className={`thread-card${thread.is_pinned ? " thread-card--pinned" : ""}`}
      onClick={() => navigate(`/thread/${thread.thread_id}`)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && navigate(`/thread/${thread.thread_id}`)}
    >
      {/* Left: title + meta */}
      <div className="thread-card-main">
        <div className="thread-card-title-row">
          {thread.is_pinned && <span className="thread-pin-badge">📌 pinned</span>}
          <span className="thread-card-title">{thread.title}</span>
        </div>
        <span className="thread-card-author">by {thread.author_username}</span>
      </div>

      {/* Right: stats + activity */}
      <div className="thread-card-right">
        <div className="thread-card-stats">
          <div className="thread-stat">
            <span className="thread-stat-value">{thread.reply_count}</span>
            <span className="thread-stat-label">replies</span>
          </div>
          <div className="thread-stat">
            <span className={`thread-stat-value${netVotes > 0 ? " thread-stat--positive" : netVotes < 0 ? " thread-stat--negative" : ""}`}>
              {netVotes > 0 ? `+${netVotes}` : netVotes}
            </span>
            <span className="thread-stat-label">votes</span>
          </div>
        </div>
        <div className="thread-card-activity">
          <span className="thread-activity-time">
            {formatActivity(thread.last_activity_at)}
          </span>
          {thread.last_reply_username ? (
            <span className="thread-activity-user">
              by {thread.last_reply_username}
            </span>
          ) : (
            <span className="thread-activity-none">no recent replies</span>
          )}
        </div>
      </div>
    </div>
  );
}