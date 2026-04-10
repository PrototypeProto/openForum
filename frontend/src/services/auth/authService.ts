import type {
  UserLogin,
  LoginResponse,
  UserSignup,
  SignupResponse,
  APIResponse,
  AuthenticatedUser,
} from "../../types/authType";
import { postJSON, getJSON } from "../../utils/fetchHelper";
import { API } from "../endpoints/api";

export async function login(
  body: UserLogin,
): Promise<APIResponse<LoginResponse>> {
  return postJSON<LoginResponse>(API.auth.login, body);
}

export async function signup(
  body: UserSignup,
): Promise<APIResponse<SignupResponse>> {
  return postJSON<SignupResponse>(API.auth.signup, body);
}

export async function logout(): Promise<APIResponse<{ message: string }>> {
  // Credentials: "include" is set in postJSON's BASE_OPTIONS so the
  // access_token cookie is sent automatically. The backend blocklists
  // the JTI and clears both cookies in the response.
  return postJSON<{ message: string }>(API.auth.logout, {});
}

export async function getMe(): Promise<APIResponse<AuthenticatedUser>> {
  return getJSON<AuthenticatedUser>(API.auth.me);
}
