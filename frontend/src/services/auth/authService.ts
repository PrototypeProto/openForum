import type {
  UserLogin,
  LoginResponse,
  LogoutAuthData,
  UserSignup,
  SignupResponse,
  APIResponse,
} from "../../types/authType";
import { postJSON } from "../../utils/fetchHelper";
import { API } from "../endpoints/api";

export async function login(body: UserLogin): Promise<APIResponse<LoginResponse>> {
  return postJSON<LoginResponse>(API.auth.login, body);
}

export async function signup(body: UserSignup): Promise<APIResponse<SignupResponse>> {
  return postJSON<SignupResponse>(API.auth.signup, body);
}

export async function logout(data: LogoutAuthData) {
  return postJSON<LogoutAuthData>(API.auth.logout, data);
}
