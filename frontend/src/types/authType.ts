export interface APIResponse<T> {
  data: T | null
  ok: boolean
  error: string | null
}

// Request bodies
export interface UserLogin {
  username: string
  password: string
}

// Success response
export interface LoginResponse {
  message: string
  access_token: string
  refresh_token: string
  user: AuthenticatedUser
}

export interface UserSignup {
  username: string
  password: string
  email: string
  nickname: string
  request: string
}

export interface SignupResponse {
  username: string
  email: string
  nickname: string
  user_id: AuthenticatedUser
}

// Default data when not logged in or authentication expired
export const EXPIRED_USER: AuthenticatedUser = {user_id: "Guest", username: "Guest", role: "", nickname: "Guest"}
export interface AuthenticatedUser {
  user_id: string
  username: string
  role: string
  nickname: string | null
}

// FastAPI validation error
export interface FastAPIError {
  detail: {
    loc: [string, number]
    msg: string
    type: string
  }[]
}

export interface LogoutAuthData {
  user_id: string
  access_token: string
  refresh_token: string
}