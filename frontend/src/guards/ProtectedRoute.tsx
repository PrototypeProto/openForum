import { type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthContext } from "../context/AuthContext";

interface Props {
  children: ReactNode
}

export function ProtectedRoute({children}: Props) {
  const { authData } = useAuthContext();
  if (!authData) return <Navigate to="/login" />;
  return children;
}
