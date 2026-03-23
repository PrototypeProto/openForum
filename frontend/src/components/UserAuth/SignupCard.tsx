import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

export default function SignupCard() {
  const navigate = useNavigate();
  const {handleSignup} = useAuth();

  const [username, setUsername] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [confirmPassword, setconfirmPassword] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [nickname, setNickname] = useState<string>("");
  const [request, setRequest] = useState<string>("");

  const [err, setErr] = useState<boolean>(false);

  const handleSignupSubmit = async () => {
    if (!username || !password || !confirmPassword) {
      setErr(true);
      return;
    }
    if (password !== confirmPassword) {
      setErr(true);
      return;
    }
    if (await handleSignup({ username, password, email, nickname, request })) {
      navigate("/account-pending-approval");
      setErr(false);
    } 
    setErr(true);

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
        type="text"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />

      <input
        type="text"
        placeholder="Confirm Password"
        value={confirmPassword}
        onChange={(e) => setconfirmPassword(e.target.value)}
      />

      <input
        type="text"
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />

      <input
        type="text"
        placeholder="Nickname"
        value={nickname}
        onChange={(e) => setNickname(e.target.value)}
      />

      <input
        type="text"
        placeholder="Request to Josh"
        value={request}
        onChange={(e) => setRequest(e.target.value)}
      />

       {/* Add custom error responses */}
      <button onClick={handleSignupSubmit}>Sign up</button><br/>
      {err && (<span>Failed to sign up try again</span>)}
    </div>
  );
}
