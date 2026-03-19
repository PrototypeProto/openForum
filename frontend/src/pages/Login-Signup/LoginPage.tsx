import { useState } from "react";
import LoginCard from "../../components/UserAuth/LoginCard";
import SignupCard from "../../components/UserAuth/SignupCard";

export default function LoginPage() {
  const [useLogin, setUseLogin] = useState<boolean>(true);

  const handleCardState = () => {
    setUseLogin(useLogin !== true);
  };

  return (
    <>
      {useLogin ? <LoginCard /> : <SignupCard />}
      <button onClick={handleCardState}>
        {useLogin == true
          ? "Don't have an account? Create one here"
          : "Have an account? Click here to log in"}
      </button>
    </>
  );
}
