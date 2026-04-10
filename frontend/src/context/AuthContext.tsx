import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import { EXPIRED_USER, type AuthenticatedUser } from "../types/authType";
import { useNavigate } from "react-router-dom";
import { logout as apiLogout, getMe } from "../services/auth/authService";

interface AuthContextType {
  authData: AuthenticatedUser | null;
  setAuthData: (data: AuthenticatedUser | null) => void;
  getUsernameOrGuest: () => string;
  logout: () => Promise<void>;
  sessionLoading: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [authData, setAuthDataState] = useState<AuthenticatedUser | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const navigate = useNavigate();

  const setAuthData = useCallback((data: AuthenticatedUser | null) => {
    setAuthDataState(data);
  }, []);

  // On mount, verify the session is still valid by calling /auth/me.
  // This is the single source of truth for whether the user is logged in —
  // localStorage is not used because it can't reflect cookie revocation.
  // Token rotation is handled transparently by the server middleware, so
  // a 401 here means the session is genuinely over.
  useEffect(() => {
    async function verifySession() {
      const res = await getMe();
      if (res.ok && res.data) {
        setAuthDataState(res.data);
      } else {
        setAuthDataState(null);
      }
      setSessionLoading(false);
    }
    verifySession();
  }, []);

  const logout = useCallback(async () => {
    // Tell the backend to blocklist the JTI and clear the cookies.
    // We navigate regardless of whether the API call succeeds —
    // worst case the cookie expires naturally.
    await apiLogout();
    setAuthDataState(null);
    navigate("/logged-out");
  }, [navigate]);

  const getUsernameOrGuest = useCallback(() => {
    return authData?.username ?? EXPIRED_USER.username;
  }, [authData]);

  return (
    <AuthContext.Provider
      value={{
        authData,
        setAuthData,
        logout,
        getUsernameOrGuest,
        sessionLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context)
    throw new Error("useAuthContext must be used inside AuthProvider");
  return context;
}
