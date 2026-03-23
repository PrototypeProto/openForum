import { type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthContext } from "../context/AuthContext";

interface Props {
  children: ReactNode
}

export function AdminRoute({children}: Props) {
  const { authData } = useAuthContext();
  if (!authData) return <Navigate to="/login" />;
  if (authData.role !== "admin") return <Navigate to="/dashboard" />;
  return children;
}
