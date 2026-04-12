import { useNavigate } from "react-router-dom";
import { useAuthContext } from "../context/AuthContext";
import "./navbar.css";

export function Navbar() {
  const navigate = useNavigate();
  const { authData, logout, sessionLoading } = useAuthContext();

  // Render a stable placeholder while the session check is in flight.
  // Without this the navbar briefly shows the logged-out state on every
  // page load/refresh before /auth/me responds, causing a visible flash.
  if (sessionLoading) {
    return (
      <nav className="navbar">
        <div className="navbar-brand">Jo.sh</div>
        <div className="navbar-links" />
        <div className="navbar-auth" />
      </nav>
    );
  }

  return (
    <nav className="navbar">
      <div className="navbar-brand">Jo.sh</div>

      <div className="navbar-links">
        <a href="/">Home</a>
        <a href="/about">About</a>
        {authData?.username && (
          <>
            <a href="/forum">Forum</a>
            <a href="/media">Media</a>
            <a href="/file-share">Temporary File Storage</a>
          </>
        )}
      </div>

      <div className="navbar-auth">
        {authData?.username ? (
          <>
            <button
              className="btn-profile"
              onClick={() => navigate("/profile")}
            >
              {authData.username}
            </button>
            <button className="btn-secondary" onClick={logout}>
              Log out
            </button>
          </>
        ) : (
          <button className="btn-primary" onClick={() => navigate("/login")}>
            Log in
          </button>
        )}
      </div>
    </nav>
  );
}
