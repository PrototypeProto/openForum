import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

export default function SignupCard() {
  const navigate = useNavigate();
  const { handleSignup } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [email, setEmail] = useState("");
  const [nickname, setNickname] = useState("");
  const [request, setRequest] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const handleSignupSubmit = async () => {
    setErr(null);

    if (!username || !password || !confirmPassword) {
      setErr("Username and password are required.");
      return;
    }
    if (password !== confirmPassword) {
      setErr("Passwords do not match.");
      return;
    }

    const response = await handleSignup({
      username,
      password,
      email: email || null,
      nickname: nickname || null,
      request: request || null,
    });

    if (response.ok) {
      // Store the username so AccountVerificationPage can display it.
      // Only the username is stored — no password, no token, no role.
      localStorage.setItem("temp_user", JSON.stringify({ username }));
      navigate("/account-pending-approval");
    } else {
      setErr(response.error ?? "Failed to sign up. Please try again.");
    }
  };

  return (
    <div className="signup-card">
      <h1>Sign Up</h1>

      <input
        type="text"
        placeholder="Username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
      />

      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />

      <input
        type="password"
        placeholder="Confirm Password"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
      />

      <input
        type="email"
        placeholder="Email (optional)"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />

      <input
        type="text"
        placeholder="Nickname (optional)"
        value={nickname}
        onChange={(e) => setNickname(e.target.value)}
      />

      <input
        type="text"
        placeholder="Request to admin"
        value={request}
        onChange={(e) => setRequest(e.target.value)}
      />

      <button onClick={handleSignupSubmit}>Sign up</button>
      {err && <span className="signup-error">{err}</span>}
    </div>
  );
}
