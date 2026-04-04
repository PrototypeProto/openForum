import { useState, useEffect } from "react";
import { getTopicGroups, getTopics } from "../services/forum/forumService";
import type { TopicGroup, Topic } from "../types/forumTypes";

export interface GroupWithTopics {
  group: TopicGroup;
  topics: Topic[];
}

interface UseForumIndexResult {
  groups: GroupWithTopics[];
  loading: boolean;
  error: string | null;
}

export function useForumIndex(): UseForumIndexResult {
  const [groups, setGroups] = useState<GroupWithTopics[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetch() {
      setLoading(true);
      setError(null);

      const groupsRes = await getTopicGroups();
      if (!groupsRes.ok || !groupsRes.data) {
        setError(groupsRes.error ?? "Failed to load forum");
        setLoading(false);
        return;
      }

      const topicsRes = await getTopics();
      if (!topicsRes.ok || !topicsRes.data) {
        setError(topicsRes.error ?? "Failed to load topics");
        setLoading(false);
        return;
      }

      const topicsByGroup = topicsRes.data.reduce<Record<string, Topic[]>>(
        (acc, topic) => {
          const key = topic.group_id ?? "__ungrouped__";
          if (!acc[key]) acc[key] = [];
          acc[key].push(topic);
          return acc;
        },
        {},
      );

      const merged: GroupWithTopics[] = groupsRes.data.map((group) => ({
        group,
        topics: topicsByGroup[group.group_id] ?? [],
      }));

      setGroups(merged);
      setLoading(false);
    }

    fetch();
  }, []);

  return { groups, loading, error };
}