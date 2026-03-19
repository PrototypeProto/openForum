import type { APIResponse, LoginResponse, SignupResponse, UserLogin, UserSignup } from "../types/authType";
import { login, signup } from "../services/auth/authService";
import { useAuthContext } from "../context/AuthContext";

export function useAuth() {
  const { setAuthData, setTokens } = useAuthContext();

  const handleLogin = async ({ username, password }: UserLogin): Promise<boolean> => {
    try {
      const response: APIResponse<LoginResponse> = await login({ username, password });
      // on successful login, response has a user field
      if (response.ok && response.data) {
        setTokens(response.data?.access_token, response.data.refresh_token);
        setAuthData(response.data.user);
        localStorage.setItem("user", JSON.stringify(response.data.user));
        localStorage.removeItem("temp_user");
        return true;
      }

      console.log(response);
      return false;
    } catch {
      return false;
    }
  };

  const handleSignup = async (userData : UserSignup): Promise<boolean> => {
    try {
      const response: APIResponse<SignupResponse> = await signup(userData);
      if (response.ok && response.data) {
        localStorage.setItem("temp_user", JSON.stringify(response.data));
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }

  return { handleLogin, handleSignup };
}
