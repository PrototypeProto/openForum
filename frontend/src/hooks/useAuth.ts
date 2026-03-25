import type {
  APIResponse,
  APISimplifiedResponse,
  LoginResponse,
  SignupResponse,
  UserLogin,
  UserSignup,
} from "../types/authType";
import { login, signup } from "../services/auth/authService";
import { useAuthContext } from "../context/AuthContext";
import { status500 } from "../types/errorType";

export function useAuth() {
  const { setAuthData, setTokens, accessToken } = useAuthContext();

  const handleLogin = async ({
    username,
    password,
  }: UserLogin): Promise<APISimplifiedResponse> => {
    try {
      const response: APIResponse<LoginResponse> = await login({
        username,
        password,
      });
      // on successful login, response has a user field
      if (response.ok && response.data) {
        setTokens(response.data.access_token, response.data.refresh_token);
        setAuthData(response.data.user);
        console.log(response)
        console.log(response.data.access_token)
        console.log(accessToken)
        localStorage.setItem("user", JSON.stringify(response.data.user));
        localStorage.removeItem("temp_user");
      }
      return {
        ok: response.ok,
        statusCode: response.statusCode,
        error: response.error,
      };
    } catch {
      return { ok: false, statusCode: 404, error: status500 };
    }
  };

  const handleSignup = async (
    userData: UserSignup,
  ): Promise<APISimplifiedResponse> => {
    try {
      if (userData.email == "") userData.email = null;
      if (userData.nickname == "") userData.nickname = null;
      if (userData.request == "") userData.request = null;

      const response: APIResponse<SignupResponse> = await signup(userData);
      if (response.ok && response.data) {
        localStorage.setItem("temp_user", JSON.stringify(response.data));
      }
      return {
        ok: response.ok,
        statusCode: response.statusCode,
        error: response.error,
      };
    } catch {
      return { ok: false, statusCode: 404, error: status500 };
    }
  };

  return { handleLogin, handleSignup };
}
