export interface APIResponse<T> {
  data: T | null;
  ok: boolean;
  statusCode: number;
  error: string | null;
}

export interface APISimplifiedResponse {
  ok: boolean;
  statusCode: number;
  error: string | null;
}

// Request bodies
export interface UserLogin {
  username: string;
  password: string;
}

export interface UserSignup {
  username: string;
  password: string;
  email: string | null;
  nickname: string | null;
  request: string | null;
}

// Login response — tokens are HttpOnly cookies set by the server,
// not returned in the body. The body only carries the user object.
export interface LoginResponse {
  message: string;
  user: AuthenticatedUser;
}

export interface SignupResponse {
  username: string;
  email: string;
  nickname: string;
  user_id: string;
}

// The authenticated user shape, sourced from login response or GET /auth/me.
// Role comes from the server, never from a token claim.
export interface AuthenticatedUser {
  user_id: string;
  username: string;
  role: string;
  nickname: string | null;
}

// Default state when not logged in
export const EXPIRED_USER: AuthenticatedUser = {
  user_id: "Guest",
  username: "Guest",
  role: "",
  nickname: "Guest",
};

// FastAPI validation error
export interface FastAPIError {
  detail: {
    loc: [string, number];
    msg: string;
    type: string;
  }[];
}
