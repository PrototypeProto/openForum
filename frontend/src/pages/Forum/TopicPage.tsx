import { useParams, useNavigate } from "react-router-dom";
import { Navbar } from "../../components/Navbar";
import ThreadCard from "../../components/forum/ThreadCard";
import { useTopicThreads } from "../../hooks/useTopicThreads";
import "./TopicPage.css";

function PageNav({
  page,
  pages,
  goToPage,
}: {
  page: number;
  pages: number;
  goToPage: (p: number) => void;
}) {
  if (pages <= 1) return <span className="topic-page-single">Page 1</span>;

  const range: (number | "...")[] = [];
  const add = new Set<number>();
  for (let i = Math.max(1, page - 2); i <= Math.min(pages, page + 2); i++) add.add(i);
  add.add(pages);

  let prev: number | null = null;
  for (const n of Array.from(add).sort((a, b) => a - b)) {
    if (prev !== null && n - prev > 1) range.push("...");
    range.push(n);
    prev = n;
  }

  return (
    <div className="topic-page-nav">
      {/* Hidden (not just disabled) when on page 1 */}
      {page > 1 && (
        <button className="page-btn" onClick={() => goToPage(page - 1)}>
          ← Prev
        </button>
      )}

      {range.map((item, i) =>
        item === "..." ? (
          <span key={`ellipsis-${i}`} className="page-ellipsis">…</span>
        ) : (
          <button
            key={item}
            className={`page-btn${item === page ? " page-btn--active" : ""}`}
            onClick={() => goToPage(item)}
          >
            {item}
          </button>
        ),
      )}

      {/* Hidden when on last page */}
      {page < pages && (
        <button className="page-btn" onClick={() => goToPage(page + 1)}>
          Next →
        </button>
      )}
    </div>
  );
}

export default function TopicPage() {
  const { topicName } = useParams<{ topicName: string }>();
  const navigate = useNavigate();
  const { topic, threads, page, pages, total, loading, error, goToPage } =
    useTopicThreads(topicName ?? "");

  return (
    <>
      <Navbar />
      <div className="topic-page">
        {/* Breadcrumb */}
        <div className="topic-breadcrumb">
          <button className="topic-back-btn" onClick={() => navigate("/forum")}>
            ← Forum
          </button>
          {topic && <span className="topic-breadcrumb-sep">/</span>}
          {topic && <span className="topic-breadcrumb-name">{topic.name}</span>}
        </div>

        {/* Header */}
        {topic && (
          <div className="topic-header">
            <div className="topic-header-left">
              {topic.icon_url && (
                <img src={topic.icon_url} alt="" className="topic-header-icon" />
              )}
              <div>
                <h1 className="topic-header-title">{topic.name}</h1>
                {topic.description && (
                  <p className="topic-header-desc">{topic.description}</p>
                )}
              </div>
            </div>
            <div className="topic-header-meta">
              <span>{total} thread{total !== 1 ? "s" : ""}</span>
              {topic.is_locked && (
                <span className="topic-locked-badge">locked</span>
              )}
            </div>
          </div>
        )}

        {error && <p className="topic-error">{error}</p>}

        {loading ? (
          <p className="topic-loading">Loading...</p>
        ) : (
          <>
            <div className="topic-thread-list">
              {threads.length === 0 ? (
                <p className="topic-empty">No threads yet. Be the first to post.</p>
              ) : (
                threads.map((thread) => (
                  <ThreadCard key={thread.thread_id} thread={thread} />
                ))
              )}
            </div>

            <div className="topic-footer">
              <PageNav page={page} pages={pages} goToPage={goToPage} />
            </div>
          </>
        )}
      </div>
    </>
  );
}