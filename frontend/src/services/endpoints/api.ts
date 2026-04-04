import type { Role } from "../../types/userTypes";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const AUTH_URL  = `${BASE_URL}/auth`;
const MEDIA_URL = `${BASE_URL}/media`;
const ADMIN_URL = `${BASE_URL}/admin`;
const FORUM_URL = `${BASE_URL}/forum`;

export const API = {
  auth: {
    signup:        `${AUTH_URL}/signup`,
    login:         `${AUTH_URL}/login`,
    logout:        `${AUTH_URL}/logout`,
    refresh_token: `${AUTH_URL}/refresh_token`,
    me:            `${AUTH_URL}/me`,
  },
  media: {
    pageCt:     `${MEDIA_URL}/pages`,
    list:       `${MEDIA_URL}/list`,
    getFile:    (filename: string) => `${MEDIA_URL}/${filename}`,
    uploadFile: `${MEDIA_URL}/file`,
    deleteFile: (filename: string) => `${MEDIA_URL}/file/${filename}`,
  },
  admin: {
    promoteToUser:        (username: string)         => `${ADMIN_URL}/${username}/promotion/user`,
    updateUserPermission: (username: string, role: Role) => `${ADMIN_URL}/${username}/promotion/${role}`,
    allUsers:             `${ADMIN_URL}/all_users`,
    allUnapprovedUsers:   `${ADMIN_URL}/unapproved/users`,
  },
  forum: {
    groups:          `${FORUM_URL}/groups`,
    topics:          `${FORUM_URL}/topics`,
    threadsByTopic:  (topicId: string)  => `${FORUM_URL}/topics/${topicId}/threads`,
    thread:          (threadId: string) => `${FORUM_URL}/threads/${threadId}`,
    repliesByThread: (threadId: string) => `${FORUM_URL}/threads/${threadId}/replies`,
    replyParent:     (replyId: string)  => `${FORUM_URL}/replies/${replyId}/parent`,
    voteThread:      (threadId: string) => `${FORUM_URL}/threads/${threadId}/vote`,
    voteReply:       (replyId: string)  => `${FORUM_URL}/replies/${replyId}/vote`,
    createThread:    (topicId: string)  => `${FORUM_URL}/topics/${topicId}/threads`,
    createReply:     (threadId: string) => `${FORUM_URL}/threads/${threadId}/replies`,
    updateThread:    (threadId: string) => `${FORUM_URL}/threads/${threadId}`,
    updateReply:     (replyId: string)  => `${FORUM_URL}/replies/${replyId}`,
    deleteThread:    (threadId: string) => `${FORUM_URL}/threads/${threadId}`,
    deleteReply:     (replyId: string)  => `${FORUM_URL}/replies/${replyId}`,
  },
};