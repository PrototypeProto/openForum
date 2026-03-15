import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { useAuthContext } from "../../context/AuthContext";

export default function LoginPage() {
  const navigate = useNavigate();
  const { authData } = useAuthContext();

  const { handleLogin } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async () => {
    if (await handleLogin({ username, password })) navigate("/profile");
    navigate("/");
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Login</h1>

        {authData && <p className="login-error"></p>}

        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />

        <input
          type="text"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <button onClick={handleSubmit}>Log in</button>
      </div>
    </div>
  );
}
