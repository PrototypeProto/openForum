import { useParams, useNavigate } from "react-router-dom";
import { Navbar } from "../../components/Navbar";
import ReplyCard from "../../components/forum/ReplyCard";
import ReplyBox from "../../components/forum/ReplyBox";
import { useThreadPage } from "../../hooks/useThreadPage";
import { useAuthContext } from "../../context/AuthContext";
import type { ReplyRead } from "../../types/forumTypes";
import "./ThreadPage.css";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function PageNav({
  page,
  pages,
  goToPage,
}: {
  page: number;
  pages: number;
  goToPage: (p: number) => void;
}) {
  if (pages <= 1) return <span className="thread-page-single">Page 1</span>;

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
    <div className="thread-page-nav">
      {/* Completely hidden when on page 1 */}
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

      {/* Completely hidden on last page */}
      {page < pages && (
        <button className="page-btn" onClick={() => goToPage(page + 1)}>
          Next →
        </button>
      )}
    </div>
  );
}

export default function ThreadPage() {
  const { threadId } = useParams<{ threadId: string }>();
  const navigate = useNavigate();
  const { authData } = useAuthContext();

  const {
    thread,
    replies,
    parentCache,
    page,
    pages,
    loading,
    repliesLoading,
    error,
    replyBody,
    setReplyBody,
    replyingTo,
    setReplyingTo,
    editingReplyId,
    editBody,
    setEditBody,
    startEdit,
    cancelEdit,
    goToPage,
    submitReply,
    submitEdit,
    submitDelete,
    submitThreadVote,
    submitReplyVote,
    threadVote,
    replyVotes,
    submitError,
  } = useThreadPage(threadId ?? "");

  if (loading) {
    return (
      <>
        <Navbar />
        <div className="thread-page">
          <p className="thread-loading">Loading…</p>
        </div>
      </>
    );
  }

  if (error || !thread) {
    return (
      <>
        <Navbar />
        <div className="thread-page">
          <p className="thread-error">{error ?? "Thread not found"}</p>
        </div>
      </>
    );
  }

  function resolveParent(reply: ReplyRead): ReplyRead | null {
    if (!reply.parent_reply_id) return null;
    const onPage = replies.find((r) => r.reply_id === reply.parent_reply_id);
    if (onPage) return onPage;
    return parentCache[reply.parent_reply_id] ?? null;
  }

  function scrollToReplyBox() {
    document.getElementById("reply-box")?.scrollIntoView({ behavior: "smooth" });
  }

  // Synthetic OP card built from thread data.
  // upvote_count/downvote_count are taken from the thread state so they stay
  // in sync after the user votes on the thread.
  const opCard: ReplyRead = {
    reply_id: thread.thread_id,
    thread_id: thread.thread_id,
    author_id: thread.author_id,
    author_username: thread.author_username,
    parent_reply_id: null,
    parent_author_username: null,
    body: thread.body,
    is_deleted: thread.is_deleted,
    created_at: thread.created_at,
    updated_at: thread.updated_at,
    reply_number: 1,
    upvote_count: thread.upvote_count,
    downvote_count: thread.downvote_count,
  };

  return (
    <>
      <Navbar />
      <div className="thread-page">

        {/* Breadcrumb */}
        <div className="thread-breadcrumb">
          <button className="thread-back-btn" onClick={() => navigate(-1)}>← Back</button>
        </div>

        {/* Thread header */}
        <div className="thread-header">
          <div className="thread-header-title-row">
            {thread.is_pinned && <span className="thread-pin-badge">📌 pinned</span>}
            {thread.is_locked && <span className="thread-locked-badge">🔒 locked</span>}
            <h1 className="thread-title">{thread.title}</h1>
          </div>
          <div className="thread-header-meta">
            <span>Posted by <strong>{thread.author_username}</strong></span>
            <span className="thread-header-dot">·</span>
            <span>{formatDate(thread.created_at)}</span>
            <span className="thread-header-dot">·</span>
            <span>{thread.reply_count} {thread.reply_count === 1 ? "reply" : "replies"}</span>
          </div>
        </div>

        {/* Reply list */}
        {repliesLoading ? (
          <p className="thread-loading">Loading replies…</p>
        ) : (
          <div className="thread-reply-list">

            {/* OP body — rendered as the first reply card, only on page 1 */}
            {page === 1 && (
              <ReplyCard
                reply={opCard}
                isOP={true}
                currentUserId={authData?.user_id ?? null}
                parentReply={null}
                editingReplyId={editingReplyId}
                editBody={editBody}
                onSetEditBody={setEditBody}
                onStartEdit={startEdit}
                onCancelEdit={cancelEdit}
                onSubmitEdit={submitEdit}
                onReplyTo={(r) => { setReplyingTo(r); scrollToReplyBox(); }}
                onDelete={() => {}}
                onVote={(_id, isUpvote) => submitThreadVote(isUpvote)}
                userVote={threadVote}
              />
            )}

            {/* Paginated replies */}
            {replies.map((reply) => (
              <ReplyCard
                key={reply.reply_id}
                reply={reply}
                isOP={reply.author_id === thread.author_id}
                currentUserId={authData?.user_id ?? null}
                parentReply={resolveParent(reply)}
                editingReplyId={editingReplyId}
                editBody={editBody}
                onSetEditBody={setEditBody}
                onStartEdit={startEdit}
                onCancelEdit={cancelEdit}
                onSubmitEdit={submitEdit}
                onReplyTo={(r) => { setReplyingTo(r); scrollToReplyBox(); }}
                onDelete={submitDelete}
                onVote={submitReplyVote}
                userVote={replyVotes[reply.reply_id] ?? null}
              />
            ))}

          </div>
        )}

        {/* Pagination + reply box */}
        <div className="thread-footer">
          <PageNav page={page} pages={pages} goToPage={goToPage} />

          <div id="reply-box">
            <ReplyBox
              body={replyBody}
              onBodyChange={setReplyBody}
              replyingTo={replyingTo}
              onClearReplyingTo={() => setReplyingTo(null)}
              onSubmit={submitReply}
              isLocked={thread.is_locked}
              submitError={submitError}
            />
          </div>
        </div>

      </div>
    </>
  );
}