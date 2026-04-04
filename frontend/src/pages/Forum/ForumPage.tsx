import { Navbar } from "../../components/Navbar";
import TopicGroupCard from "../../components/forum/TopicGroupCard";
import { useForumIndex } from "../../hooks/useForumIndex";
import "./ForumPage.css";

export default function ForumPage() {
  const { groups, loading, error } = useForumIndex();

  return (
    <>
      <Navbar />
      <div className="forum-page">
        <h1 className="forum-heading">The Circle</h1>

        {error && <p className="forum-error">{error}</p>}

        {loading ? (
          <p className="forum-loading">Loading...</p>
        ) : groups.length === 0 ? (
          <p className="forum-empty">Nothing here yet.</p>
        ) : (
          <div className="forum-groups">
            {groups.map(({ group, topics }) => (
              <TopicGroupCard key={group.group_id} data={{ group, topics }} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}