

// Request bodies
export interface LoginBody {
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