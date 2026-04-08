export interface UserStats {
  unverified: number;
  user: number;
  vip: number;
  admins: number;
}

export interface UserRead {
  user_id: string
  username: string
  nickname: string | null
  join_date: string
  role: string
}

export interface PendingUserRead {
  user_id: string
  username: string
  email: string | null
  nickname: string | null
  join_date: string
  request: string | null
}

export interface RejectedUserRead {
  user_id: string
  username: string
  email: string | null
  nickname: string | null
  join_date: string
  request: string | null
  rejected_date: string
}