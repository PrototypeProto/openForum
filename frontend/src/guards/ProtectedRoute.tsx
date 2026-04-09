import { type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthContext } from "../context/AuthContext";

interface Props {
  children: ReactNode;
}

export function ProtectedRoute({ children }: Props) {
  const { authData, sessionLoading } = useAuthContext();

  // Wait for the /me check to complete before redirecting —
  // avoids a flash-redirect to /login on every page refresh.
  if (sessionLoading) return null;

  if (!authData) return <Navigate to="/login" />;
  return children;
}
