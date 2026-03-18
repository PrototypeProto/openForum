import { useNavigate } from "react-router-dom";
import { useAuthContext } from "../context/AuthContext";

export function Navbar() {
  const navigate = useNavigate()
  const {authData, logout} = useAuthContext();

  return (
    <nav className="navbar">
      <div className="navbar-brand">Jo.sh</div>

      <div className="navbar-links">
        <a href="/">Home</a>
        <a href="/forum">Forum</a>
        <a href="/media">Media</a>
        <a href="/file-share">Temporary File Storage</a>
      </div>

      <div className="navbar-auth">
        {authData?.username ? (
          <>
            <span className="navbar-username">{authData.username}</span>
            <button className="btn-secondary" onClick={logout}>Log out</button>
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
