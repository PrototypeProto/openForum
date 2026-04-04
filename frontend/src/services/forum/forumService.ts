import { getJSON, postJSON, patchJSON, deleteReq } from "../../utils/fetchHelper";
import { API } from "../endpoints/api";
import type { APIResponse } from "../../types/authType";
import type {
  TopicGroup,
  Topic,
  PaginatedThreads,
  ThreadRead,
  ReplyRead,
  PaginatedReplies,
  ReplyCreatePayload,
  ReplyUpdatePayload,
  VotePayload,
  VoteResult,
} from "../../types/forumTypes";

export async function getTopicGroups(): Promise<APIResponse<TopicGroup[]>> {
  return getJSON<TopicGroup[]>(API.forum.groups);
}

export async function getTopics(groupId?: string): Promise<APIResponse<Topic[]>> {
  return getJSON<Topic[]>(API.forum.topics, groupId ? { group_id: groupId } : undefined);
}

export async function getThreads(
  topicId: string,
  page: number,
): Promise<APIResponse<PaginatedThreads>> {
  return getJSON<PaginatedThreads>(API.forum.threadsByTopic(topicId), { page });
}

export async function getThread(threadId: string): Promise<APIResponse<ThreadRead>> {
  return getJSON<ThreadRead>(API.forum.thread(threadId));
}

export async function getReplies(
  threadId: string,
  page: number,
): Promise<APIResponse<PaginatedReplies>> {
  return getJSON<PaginatedReplies>(API.forum.repliesByThread(threadId), { page });
}

export async function getReplyParent(replyId: string): Promise<APIResponse<ReplyRead>> {
  return getJSON<ReplyRead>(API.forum.replyParent(replyId));
}

export async function createReply(
  threadId: string,
  payload: ReplyCreatePayload,
): Promise<APIResponse<ReplyRead>> {
  return postJSON<ReplyRead>(API.forum.createReply(threadId), payload);
}

export async function updateReply(
  replyId: string,
  payload: ReplyUpdatePayload,
): Promise<APIResponse<ReplyRead>> {
  return patchJSON<ReplyRead>(API.forum.updateReply(replyId), payload);
}

export async function deleteReply(replyId: string): Promise<APIResponse<null>> {
  return deleteReq(API.forum.deleteReply(replyId));
}

export async function voteThread(
  threadId: string,
  payload: VotePayload,
): Promise<APIResponse<VoteResult>> {
  return postJSON<VoteResult>(API.forum.voteThread(threadId), payload);
}

export async function voteReply(
  replyId: string,
  payload: VotePayload,
): Promise<APIResponse<VoteResult>> {
  return postJSON<VoteResult>(API.forum.voteReply(replyId), payload);
}