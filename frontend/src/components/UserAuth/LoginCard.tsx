import { useState } from "react";
import { useAuth } from "../../hooks/useAuth";
import { useNavigate } from "react-router-dom";

export default function LoginCard() {
  const navigate = useNavigate();
  
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [err, setErr] = useState<boolean>(false);

  const { handleLogin } = useAuth();

  const handleLoginSubmit = async () => {
    if (await handleLogin({ username, password })) {
      navigate("/profile");
      setErr(false);
    } 
    setErr(true);
  };

  return (
    <div className="login-card">
      <h1>Login</h1>

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

      <button onClick={handleLoginSubmit}>Log in</button><br/>
      {err && (<span>Failed to login, try again</span>)}

    </div>
  );
}
