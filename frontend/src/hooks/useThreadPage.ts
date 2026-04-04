import { useState, useEffect, useCallback } from "react";
import {
  getThread,
  getReplies,
  getReplyParent,
  createReply,
  updateReply,
  deleteReply,
  voteThread,
  voteReply,
} from "../services/forum/forumService";
import type { ThreadRead, ReplyRead, PaginatedReplies } from "../types/forumTypes";

interface UseThreadPageResult {
  thread: ThreadRead | null
  replies: ReplyRead[]
  parentCache: Record<string, ReplyRead>
  page: number
  pages: number
  total: number
  loading: boolean
  repliesLoading: boolean
  error: string | null
  replyBody: string
  setReplyBody: (v: string) => void
  replyingTo: ReplyRead | null
  setReplyingTo: (r: ReplyRead | null) => void
  editingReplyId: string | null
  editBody: string
  setEditBody: (v: string) => void
  startEdit: (reply: ReplyRead) => void
  cancelEdit: () => void
  goToPage: (p: number) => void
  submitReply: () => Promise<void>
  submitEdit: (replyId: string) => Promise<void>
  submitDelete: (replyId: string) => Promise<void>
  submitThreadVote: (isUpvote: boolean) => Promise<void>
  submitReplyVote: (replyId: string, isUpvote: boolean) => Promise<void>
  threadVote: boolean | null
  replyVotes: Record<string, boolean | null>
  submitError: string | null
}

const PAGE_SIZE = 15;

export function useThreadPage(threadId: string): UseThreadPageResult {
  const [thread, setThread] = useState<ThreadRead | null>(null);
  const [replies, setReplies] = useState<ReplyRead[]>([]);
  const [parentCache, setParentCache] = useState<Record<string, ReplyRead>>({});
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [repliesLoading, setRepliesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [replyBody, setReplyBody] = useState("");
  const [replyingTo, setReplyingTo] = useState<ReplyRead | null>(null);

  const [editingReplyId, setEditingReplyId] = useState<string | null>(null);
  const [editBody, setEditBody] = useState("");

  const [submitError, setSubmitError] = useState<string | null>(null);
  const [threadVote, setThreadVote] = useState<boolean | null>(null);
  const [replyVotes, setReplyVotes] = useState<Record<string, boolean | null>>({});

  // Fetch thread once on mount
  useEffect(() => {
    async function fetchThread() {
      setLoading(true);
      setError(null);
      const res = await getThread(threadId);
      if (!res.ok || !res.data) {
        setError(res.error ?? "Thread not found");
        setLoading(false);
        return;
      }
      setThread(res.data);
      setLoading(false);
    }
    fetchThread();
  }, [threadId]);

  const fetchReplies = useCallback(async (targetPage: number) => {
    setRepliesLoading(true);
    const res = await getReplies(threadId, targetPage);
    if (!res.ok || !res.data) {
      setRepliesLoading(false);
      return;
    }
    const data: PaginatedReplies = res.data;
    setReplies(data.items);
    setPages(data.pages);
    setTotal(data.total);

    // Fetch any parents not present on this page
    const pageReplyIds = new Set(data.items.map((r) => r.reply_id));
    const toFetch = data.items.filter(
      (r) =>
        r.parent_reply_id !== null &&
        !pageReplyIds.has(r.parent_reply_id) &&
        !parentCache[r.parent_reply_id],
    );

    if (toFetch.length > 0) {
      const fetched = await Promise.all(
        [...new Set(toFetch.map((r) => r.parent_reply_id as string))].map(
          (id) => getReplyParent(id),
        ),
      );
      const newEntries: Record<string, ReplyRead> = {};
      fetched.forEach((res) => {
        if (res.ok && res.data) newEntries[res.data.reply_id] = res.data;
      });
      setParentCache((prev) => ({ ...prev, ...newEntries }));
    }

    setRepliesLoading(false);
  }, [threadId, parentCache]);

  useEffect(() => {
    if (!loading) fetchReplies(page);
  }, [page, loading]);

  const startEdit = useCallback((reply: ReplyRead) => {
    setEditingReplyId(reply.reply_id);
    setEditBody(reply.body);
  }, []);

  const cancelEdit = useCallback(() => {
    setEditingReplyId(null);
    setEditBody("");
  }, []);

  const submitReply = useCallback(async () => {
    if (!replyBody.trim()) return;
    setSubmitError(null);

    const res = await createReply(threadId, {
      body: replyBody.trim(),
      parent_reply_id: replyingTo?.reply_id ?? null,
    });
    if (!res.ok || !res.data) {
      setSubmitError(res.error ?? "Failed to post reply");
      return;
    }

    setReplyBody("");
    setReplyingTo(null);

    // Backend always uses PAGE_SIZE=15, so offset math is consistent across pages.
    const newTotal = total + 1;
    const newLastPage = Math.ceil(newTotal / PAGE_SIZE);

    if (newLastPage === page) {
      // Still on the last page — setPage is a no-op so call fetchReplies directly
      await fetchReplies(page);
    } else {
      // Overflowed onto a new page — triggers useEffect to fetch
      setPage(newLastPage);
    }
  }, [replyBody, replyingTo, threadId, total, page, fetchReplies]);

  const submitEdit = useCallback(
    async (replyId: string) => {
      if (!editBody.trim()) return;
      setSubmitError(null);
      const res = await updateReply(replyId, { body: editBody.trim() });
      if (!res.ok) {
        setSubmitError(res.error ?? "Failed to update reply");
        return;
      }
      setReplies((prev) =>
        prev.map((r) =>
          r.reply_id === replyId
            ? { ...r, body: editBody.trim(), updated_at: new Date().toISOString() }
            : r,
        ),
      );
      cancelEdit();
    },
    [editBody, cancelEdit],
  );

  const submitDelete = useCallback(async (replyId: string) => {
    setSubmitError(null);
    const res = await deleteReply(replyId);
    if (!res.ok) {
      setSubmitError(res.error ?? "Failed to delete reply");
      return;
    }
    setReplies((prev) =>
      prev.map((r) =>
        r.reply_id === replyId ? { ...r, is_deleted: true, body: "[deleted]" } : r,
      ),
    );
  }, []);

  const submitThreadVote = useCallback(async (isUpvote: boolean) => {
    if (!thread) return;
    const res = await voteThread(threadId, { is_upvote: isUpvote });
    if (!res.ok || !res.data) return;
    setThread((prev) =>
      prev
        ? {
            ...prev,
            upvote_count: res.data!.upvote_count,
            downvote_count: res.data!.downvote_count,
          }
        : prev,
    );
    setThreadVote(res.data.user_vote);
  }, [thread, threadId]);

  const submitReplyVote = useCallback(async (replyId: string, isUpvote: boolean) => {
    const res = await voteReply(replyId, { is_upvote: isUpvote });
    if (!res.ok || !res.data) return;
    setReplies((prev) =>
      prev.map((r) =>
        r.reply_id === replyId
          ? {
              ...r,
              upvote_count: res.data!.upvote_count,
              downvote_count: res.data!.downvote_count,
            }
          : r,
      ),
    );
    setReplyVotes((prev) => ({ ...prev, [replyId]: res.data!.user_vote }));
  }, []);

  return {
    thread,
    replies,
    parentCache,
    page,
    pages,
    total,
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
    goToPage: setPage,
    submitReply,
    submitEdit,
    submitDelete,
    submitThreadVote,
    submitReplyVote,
    threadVote,
    replyVotes,
    submitError,
  };
}