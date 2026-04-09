import { type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthContext } from "../context/AuthContext";
import { Role } from "../types/userTypes";

interface Props {
  children: ReactNode;
}

export function AdminRoute({ children }: Props) {
  const { authData, sessionLoading } = useAuthContext();

  if (sessionLoading) return null;

  if (!authData) return <Navigate to="/login" />;
  // Role comes from /auth/me (live, server-sourced) — never from a token claim.
  if (authData.role !== Role.ADMIN) return <Navigate to="/profile" />;
  return children;
}
