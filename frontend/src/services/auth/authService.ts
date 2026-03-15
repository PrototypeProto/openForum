import type { LoginBody, LoginResponse, LogoutAuthData } from "../../types/authType";
import { postJSON } from "../../utils/fetchHelper";
import { API } from "../endpoints/api";

export async function login(body: LoginBody): Promise<LoginResponse> {
  return postJSON<LoginResponse>(API.auth.login, body)
}

export async function logout(data: LogoutAuthData) {
  return postJSON<LogoutAuthData>(API.auth.logout, data)
}