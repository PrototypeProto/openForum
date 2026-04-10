import type { Role } from "../../types/userTypes";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const AUTH_URL = `${BASE_URL}/auth`;
const MEDIA_URL = `${BASE_URL}/media`;
const ADMIN_URL = `${BASE_URL}/admin`;
const FORUM_URL = `${BASE_URL}/forum`;
const TEMPFS_URL = `${BASE_URL}/tempfs`;

export const API = {
  auth: {
    // POST /auth/signup
    signup: `${AUTH_URL}/signup`,
    // POST /auth/login
    login: `${AUTH_URL}/login`,
    // POST /auth/logout
    logout: `${AUTH_URL}/logout`,
    // POST /auth/refresh_token
    refresh_token: `${AUTH_URL}/refresh_token`,
    // GET  /auth/me
    me: `${AUTH_URL}/me`,
  },

  media: {
    // GET  /media/list?page=1  (pagination metadata should come from this response envelope)
    list: (page: number) => `${MEDIA_URL}/list?page=${page}`,
    // GET  /media/{filename}
    getFile: (filename: string) => `${MEDIA_URL}/${filename}`,
    // POST /media/file
    uploadFile: `${MEDIA_URL}/file`,
    // DELETE /media/file/{filename}
    deleteFile: (filename: string) => `${MEDIA_URL}/file/${filename}`,
  },

  admin: {
    // GET   /admin/users
    users: `${ADMIN_URL}/users`,
    // GET   /admin/users/pending
    pendingUsers: `${ADMIN_URL}/users/pending`,
    // GET   /admin/users/stats
    userStats: `${ADMIN_URL}/users/stats`,
    // PATCH /admin/users/{username}/role  body: { role }
    updateRole: (username: string) => `${ADMIN_URL}/users/${username}/role`,
    // POST  /admin/users/{username}/approve
    approveUser: (username: string) => `${ADMIN_URL}/users/${username}/approve`,
    // POST  /admin/users/{username}/reject
    rejectUser: (username: string) => `${ADMIN_URL}/users/${username}/reject`,
  },

  forum: {
    // GET  /forum/groups
    groups: `${FORUM_URL}/groups`,
    // GET  /forum/topics
    topics: `${FORUM_URL}/topics`,
    // GET  /forum/topics/{topicId}/threads?page=1
    threadsByTopic: (topicId: string) =>
      `${FORUM_URL}/topics/${topicId}/threads`,
    // GET  /forum/threads/{threadId}
    thread: (threadId: string) => `${FORUM_URL}/threads/${threadId}`,
    // POST /forum/topics/{topicId}/threads
    createThread: (topicId: string) => `${FORUM_URL}/topics/${topicId}/threads`,
    // PATCH /forum/threads/{threadId}
    updateThread: (threadId: string) => `${FORUM_URL}/threads/${threadId}`,
    // DELETE /forum/threads/{threadId}
    deleteThread: (threadId: string) => `${FORUM_URL}/threads/${threadId}`,
    // POST /forum/threads/{threadId}/vote
    voteThread: (threadId: string) => `${FORUM_URL}/threads/${threadId}/vote`,
    // GET  /forum/threads/{threadId}/replies?page=1
    repliesByThread: (threadId: string) =>
      `${FORUM_URL}/threads/${threadId}/replies`,
    // GET  /forum/replies/{replyId}/parent
    replyParent: (replyId: string) => `${FORUM_URL}/replies/${replyId}/parent`,
    // POST /forum/threads/{threadId}/replies
    createReply: (threadId: string) =>
      `${FORUM_URL}/threads/${threadId}/replies`,
    // PATCH /forum/replies/{replyId}
    updateReply: (replyId: string) => `${FORUM_URL}/replies/${replyId}`,
    // DELETE /forum/replies/{replyId}
    deleteReply: (replyId: string) => `${FORUM_URL}/replies/${replyId}`,
    // POST /forum/replies/{replyId}/vote
    voteReply: (replyId: string) => `${FORUM_URL}/replies/${replyId}/vote`,
  },

  tempfs: {
    // POST /tempfs/upload
    upload: `${TEMPFS_URL}/upload`,
    // GET  /tempfs/files
    files: `${TEMPFS_URL}/files`,
    // GET  /tempfs/storage
    storage: `${TEMPFS_URL}/storage`,
    // GET  /tempfs/files/{fileId}
    info: (fileId: string) => `${TEMPFS_URL}/files/${fileId}`,
    // GET  /tempfs/files/{fileId}/content?want_compressed=false
    // Password is sent via X-File-Password header, not in the URL
    download: (
      fileId: string,
      wantCompressed: boolean = false,
    ) => {
      const params = new URLSearchParams({
        want_compressed: String(wantCompressed),
      });
      return `${TEMPFS_URL}/files/${fileId}/content?${params.toString()}`;
    },
    // DELETE /tempfs/files/{fileId}
    delete: (fileId: string) => `${TEMPFS_URL}/files/${fileId}`,
  },
};
