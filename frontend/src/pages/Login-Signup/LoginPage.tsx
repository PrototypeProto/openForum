import { useState } from "react";
import LoginCard from "../../components/UserAuth/LoginCard";
import SignupCard from "../../components/UserAuth/SignupCard";
import "./auth.css";
import { Navbar } from "../../components/Navbar";

export default function LoginPage() {
  const [useLogin, setUseLogin] = useState<boolean>(true);

  const handleCardState = () => {
    setUseLogin(useLogin !== true);
  };

  return (
    <>
    <Navbar/>
      <div className="auth-page">
        {useLogin ? <LoginCard /> : <SignupCard />}
        <button onClick={handleCardState}>
          {useLogin == true
            ? "Don't have an account? Create one here"
            : "Have an account? Click here to log in"}
        </button>
      </div>
    </>
  );
}
