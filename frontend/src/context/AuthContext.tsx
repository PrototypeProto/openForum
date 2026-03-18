import React, { createContext, useContext, useState } from "react";
import { EXPIRED_USER, type AuthenticatedUser } from "../types/authType";
import { useNavigate } from "react-router-dom";

interface AuthContextType {
  authData: AuthenticatedUser | null;
  setAuthData: (data: AuthenticatedUser | null) => void;
  getUsernameOrGuest: () => string;
  accessToken: string | null;
  refreshToken: string | null;
  setTokens: (access: string | null, refresh: string | null) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // load from localStorage on first render
  const [authData, setUserAuthDataState] = useState<AuthenticatedUser | null>(
    () => {
      const stored = localStorage.getItem("user");
      return stored ? JSON.parse(stored) : null;
    },
  );

  const setAuthData = (data: AuthenticatedUser | null) => {
    setUserAuthDataState(data);
    localStorage.setItem("user", JSON.stringify(data));
  };

  
  const navigate = useNavigate();
  const logout = () => {
    setAuthData(null);
    localStorage.removeItem("user");
    navigate("/logged-out");
  };

  const getUsernameOrGuest = () => {
    if (!authData) return EXPIRED_USER.username;
    else return authData.username;
  };

  const [accessToken, setAccessToken] = useState<string|null>(null);
  const [refreshToken, setRefreshToken] = useState<string|null>(null);

  const setTokens = (access: string | null, refresh: string | null) => {
    setAccessToken(access);
    setRefreshToken(refresh);
  }

  return (
    <AuthContext.Provider
      value={{ authData, setAuthData, logout, getUsernameOrGuest, accessToken, refreshToken, setTokens }}
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
