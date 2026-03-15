import type { LoginResponse } from "../types/authType";
import { login } from "../services/auth/authService";
import type { UserLogin } from "../types/User";
import { useAuthContext } from "../context/AuthContext";

export function useAuth() {
  const { setAuthData, setTokens } = useAuthContext();

  const handleLogin = async ({ username, password }: UserLogin) => {
    try {
      const data: LoginResponse = await login({ username, password });
      // on successful login, response has a user field
      if (data && data.user) {
        setTokens(data.access_token, data.refresh_token);
        setAuthData(data.user);
        localStorage.setItem("user", JSON.stringify(data.user));
        return true;
      } else {
        setAuthData(null);
        sessionStorage.removeItem("user");
        console.log(data);
      }
      return false;
    } catch {
      return false;
    }
  };

  return { handleLogin };
}
