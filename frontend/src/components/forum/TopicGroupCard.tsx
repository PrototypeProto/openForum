import { useNavigate } from "react-router-dom";
import type { GroupWithTopics } from "../../hooks/useForumIndex";
import type { Topic } from "../../types/forumTypes";
import "./TopicGroupCard.css";

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

function TopicRow({ topic }: { topic: Topic }) {
  const navigate = useNavigate();
  const slug = topic.name.toLowerCase().replace(/\s+/g, "-");

  return (
    <div
      className="topic-row"
      onClick={() => navigate(`/forum/${slug}`)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && navigate(`/forum/${slug}`)}
    >
      <div className="topic-row-left">
        {topic.icon_url && (
          <img src={topic.icon_url} alt="" className="topic-icon" />
        )}
        <div className="topic-row-info">
          <span className="topic-row-name">{topic.name}</span>
          {topic.description && (
            <span className="topic-row-desc">{topic.description}</span>
          )}
        </div>
      </div>
      <div className="topic-row-right">
        <div className="topic-row-stat">
          <span className="topic-stat-value">{topic.thread_count}</span>
          <span className="topic-stat-label">threads</span>
        </div>
        <div className="topic-row-stat">
          <span className="topic-stat-value">{topic.reply_count}</span>
          <span className="topic-stat-label">replies</span>
        </div>
        <div className="topic-row-activity">
          {topic.is_locked && <span className="topic-locked-badge">locked</span>}
          <span className="topic-activity-time">
            {formatActivity(topic.last_activity_at)}
          </span>
        </div>
      </div>
    </div>
  );
}

interface TopicGroupCardProps {
  data: GroupWithTopics;
}

export default function TopicGroupCard({ data }: TopicGroupCardProps) {
  return (
    <div className="topic-group-card">
      <div className="topic-group-header">
        <span className="topic-group-name">{data.group.name}</span>
      </div>
      <div className="topic-group-body">
        {data.topics.length === 0 ? (
          <p className="topic-group-empty">No topics yet.</p>
        ) : (
          data.topics.map((topic) => (
            <TopicRow key={topic.topic_id} topic={topic} />
          ))
        )}
      </div>
    </div>
  );
}