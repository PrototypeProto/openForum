import type {
  APISimplifiedResponse,
  LoginResponse,
  UserLogin,
  UserSignup,
  SignupResponse,
  APIResponse,
} from "../types/authType";
import { login, signup } from "../services/auth/authService";
import { useAuthContext } from "../context/AuthContext";
import { status500 } from "../types/errorType";

export function useAuth() {
  const { setAuthData } = useAuthContext();

  const handleLogin = async ({
    username,
    password,
  }: UserLogin): Promise<APISimplifiedResponse> => {
    try {
      const response: APIResponse<LoginResponse> = await login({
        username,
        password,
      });

      if (response.ok && response.data) {
        // Role and user info come from the response body.
        // Tokens are HttpOnly cookies — never touch them from JS.
        setAuthData(response.data.user);
      }

      return {
        ok: response.ok,
        statusCode: response.statusCode,
        error: response.error,
      };
    } catch {
      return { ok: false, statusCode: 500, error: status500 };
    }
  };

  const handleSignup = async (
    userData: UserSignup,
  ): Promise<APISimplifiedResponse> => {
    try {
      if (userData.email === "") userData.email = null;
      if (userData.nickname === "") userData.nickname = null;
      if (userData.request === "") userData.request = null;

      const response: APIResponse<SignupResponse> = await signup(userData);

      return {
        ok: response.ok,
        statusCode: response.statusCode,
        error: response.error,
      };
    } catch {
      return { ok: false, statusCode: 500, error: status500 };
    }
  };

  return { handleLogin, handleSignup };
}
