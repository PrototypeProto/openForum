import { useState, useEffect } from "react";
import { getTopics, getThreads } from "../services/forum/forumService";
import type { Topic, ThreadListItem, PaginatedThreads } from "../types/forumTypes";

interface UseTopicThreadsResult {
  topic: Topic | null;
  threads: ThreadListItem[];
  page: number;
  pages: number;
  total: number;
  loading: boolean;
  error: string | null;
  goToPage: (p: number) => void;
}

export function useTopicThreads(topicName: string): UseTopicThreadsResult {
  const [topic, setTopic] = useState<Topic | null>(null);
  const [threads, setThreads] = useState<ThreadListItem[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Resolve topic_id from the topic name on mount
  useEffect(() => {
    async function resolveTopic() {
      const res = await getTopics();
      if (!res.ok || !res.data) {
        setError(res.error ?? "Failed to load topics");
        setLoading(false);
        return;
      }
      const match = res.data.find(
        (t) => t.name.toLowerCase().replace(/\s+/g, "-") === topicName.toLowerCase(),
      );
      if (!match) {
        setError("Topic not found");
        setLoading(false);
        return;
      }
      setTopic(match);
    }
    resolveTopic();
  }, [topicName]);

  // Fetch threads whenever topic or page changes
  useEffect(() => {
    if (!topic) return;

    async function fetchThreads() {
      setLoading(true);
      setError(null);
      const res = await getThreads(topic!.topic_id, page);
      if (!res.ok || !res.data) {
        setError(res.error ?? "Failed to load threads");
        setLoading(false);
        return;
      }
      setThreads(res.data.items);
      setPages(res.data.pages);
      setTotal(res.data.total);
      setLoading(false);
    }

    fetchThreads();
  }, [topic, page]);

  return { topic, threads, page, pages, total, loading, error, goToPage: setPage };
}