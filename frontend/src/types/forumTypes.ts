export interface TopicGroup {
  group_id: string
  name: string
  display_order: number
}

export interface Topic {
  topic_id: string
  group_id: string | null
  name: string
  description: string | null
  icon_url: string | null
  display_order: number
  thread_count: number
  reply_count: number
  is_locked: boolean
  last_activity_at: string | null
  last_thread_id: string | null
}

export interface ThreadListItem {
  thread_id: string
  title: string
  author_id: string
  author_username: string
  created_at: string
  reply_count: number
  upvote_count: number
  downvote_count: number
  is_pinned: boolean
  last_activity_at: string | null
  last_reply_username: string | null
}

export interface PaginatedThreads {
  items: ThreadListItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ThreadRead {
  thread_id: string
  topic_id: string
  author_id: string
  author_username: string
  title: string
  body: string
  created_at: string
  updated_at: string | null
  is_pinned: boolean
  is_locked: boolean
  is_deleted: boolean
  reply_count: number
  upvote_count: number
  downvote_count: number
  last_activity_at: string | null
}

export interface ReplyRead {
  reply_id: string
  thread_id: string
  author_id: string
  author_username: string
  parent_reply_id: string | null
  parent_author_username: string | null
  body: string
  is_deleted: boolean
  created_at: string
  updated_at: string | null
  reply_number: number
  upvote_count: number
  downvote_count: number
}

export interface PaginatedReplies {
  items: ReplyRead[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ReplyCreatePayload {
  body: string
  parent_reply_id: string | null
}

export interface ReplyUpdatePayload {
  body: string
}

export interface VotePayload {
  is_upvote: boolean
}

export interface VoteResult {
  upvote_count: number
  downvote_count: number
  user_vote: boolean | null  // true = upvoted, false = downvoted, null = no vote
}