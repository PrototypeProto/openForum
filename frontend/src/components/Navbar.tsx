import { useNavigate } from "react-router-dom";
import { useAuthContext } from "../context/AuthContext";

interface NavbarProps {
  username: string | null | undefined;
  // onLogin: () => void;
  // onLogout: () => void;
}

export function Navbar({ username }: NavbarProps) {
  const navigate = useNavigate()
  const {logout} = useAuthContext();

  return (
    <nav className="navbar">
      <div className="navbar-brand">Jo.sh</div>

      <div className="navbar-links">
        <a href="/forum">Forum</a>
        <a href="/media">Media</a>
        <a href="/file-share">Temporary File Storage</a>
      </div>

      <div className="navbar-auth">
        {username ? (
          <>
            <span className="navbar-username">{username}</span>
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
