/**
 * AuthContext.tsx
 * ───────────────
 * Single source of truth for the authenticated user's identity.
 *
 * Architecture
 * ────────────
 * auth data is cached in sessionStorage under SESSION_KEY so that:
 *   1. authData is available synchronously on mount — no network round-trip,
 *      no flash of the unauthenticated navbar, no sessionLoading delay on
 *      navigation between pages.
 *   2. The cache is tab-scoped (sessionStorage clears on tab close),
 *      so stale data never bleeds between sessions.
 *
 * On first load (cold cache) we call /auth/me once to hydrate the store,
 * then cache the result. On subsequent navigations the cached value is used
 * directly — sessionLoading is false from the first render.
 *
 * Invalidation
 * ────────────
 * The backend is the authority on auth state. Two paths keep the cache honest:
 *
 *   a) Role change / token revocation → backend returns 401 on the next
 *      request. The 401 handler in fetchHelper.ts calls clearSession() which
 *      wipes the cache and redirects to /login. The user re-authenticates and
 *      gets fresh data from the login response body.
 *
 *   b) Normal logout → logout() clears the cache and navigates to /logged-out.
 *
 * We never need to poll /auth/me. Every API call already goes through the
 * backend auth middleware, so the backend always enforces the live auth state.
 * /auth/me is only used as the cold-start hydration call.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
} from "react";
import { EXPIRED_USER, type AuthenticatedUser } from "../types/authType";
import { useNavigate } from "react-router-dom";
import { logout as apiLogout, getMe } from "../services/auth/authService";

// ── Session cache ─────────────────────────────────────────────────────────────

const SESSION_KEY = "auth_user";

function readCache(): AuthenticatedUser | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as AuthenticatedUser) : null;
  } catch {
    return null;
  }
}

function writeCache(data: AuthenticatedUser): void {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
  } catch {
    // sessionStorage unavailable (private browsing edge cases) — degrade gracefully
  }
}

export function clearSession(): void {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // ignore
  }
}

// ── Context ───────────────────────────────────────────────────────────────────

interface AuthContextType {
  authData: AuthenticatedUser | null;
  setAuthData: (data: AuthenticatedUser | null) => void;
  getUsernameOrGuest: () => string;
  logout: () => Promise<void>;
  /** False once we know whether the user is logged in or not.
   *  Only true on a cold start while the /auth/me call is in flight.
   *  Will be false immediately on subsequent navigations (cache hit). */
  sessionLoading: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Initialise from cache synchronously — this is the key change.
  // On a cache hit, authData is populated before the first render and
  // sessionLoading is false immediately, so the navbar and guards never
  // see a transient null/loading state on navigation.
  const cached = readCache();
  const [authData, setAuthDataState] = useState<AuthenticatedUser | null>(
    cached,
  );
  const [sessionLoading, setSessionLoading] = useState(cached === null);

  const navigate = useNavigate();

  const setAuthData = useCallback((data: AuthenticatedUser | null) => {
    setAuthDataState(data);
    if (data) {
      writeCache(data);
    } else {
      clearSession();
    }
  }, []);

  // Cold-start hydration: only call /auth/me when there is no cached data.
  // StrictMode double-invoke guard prevents a second call in development.
  const sessionChecked = useRef(false);

  useEffect(() => {
    // Cache hit — nothing to do. sessionLoading is already false.
    if (cached !== null) return;

    if (sessionChecked.current) return;
    sessionChecked.current = true;

    async function hydrate() {
      const res = await getMe();
      if (res.ok && res.data) {
        setAuthData(res.data);
      } else {
        setAuthDataState(null);
      }
      setSessionLoading(false);
    }
    hydrate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    clearSession();
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
