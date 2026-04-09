import { type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthContext } from "../context/AuthContext";

interface Props {
  children: ReactNode;
}

export function GuestRoute({ children }: Props) {
  const { authData, sessionLoading } = useAuthContext();

  if (sessionLoading) return null;

  if (authData) return <Navigate to="/profile" />;
  return children;
}
