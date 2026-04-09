import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import { EXPIRED_USER, type AuthenticatedUser } from "../types/authType";
import { useNavigate } from "react-router-dom";
import {
  logout as apiLogout,
  getMe,
  refreshToken,
} from "../services/auth/authService";
import { registerUnauthorizedHandler } from "../utils/fetchHelper";

interface AuthContextType {
  authData: AuthenticatedUser | null;
  setAuthData: (data: AuthenticatedUser | null) => void;
  getUsernameOrGuest: () => string;
  logout: () => Promise<void>;
  handleUnauthorized: () => Promise<void>;
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

  // Called by fetchHelper when any request returns 401.
  // Attempts a token rotation first; if that also fails, forces re-login.
  const handleUnauthorized = useCallback(async () => {
    const res = await refreshToken();
    if (res.ok) {
      // Rotation succeeded — fresh cookies are set. Re-fetch user data.
      const meRes = await getMe();
      if (meRes.ok && meRes.data) {
        setAuthDataState(meRes.data);
        return;
      }
    }
    // Rotation failed (reuse detected, expired, etc.) — force re-login.
    setAuthDataState(null);
    navigate("/login");
  }, [navigate]);

  // Register the 401 handler with fetchHelper once on mount.
  // This avoids a circular import while still allowing any fetch to trigger rotation.
  useEffect(() => {
    registerUnauthorizedHandler(handleUnauthorized);
  }, [handleUnauthorized]);

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
        handleUnauthorized,
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
