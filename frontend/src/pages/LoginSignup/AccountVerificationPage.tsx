import type { SignupResponse } from "../../types/authType";

export default function AccountVerificationPage() {
  const stored = localStorage.getItem("temp_user");

  const temp_user: SignupResponse | null = stored ? JSON.parse(stored) : null;

  return (
    <>
      <h1>Successfully signed up!</h1>
      {temp_user && (<span>Account "{temp_user.username}" has been created</span>)}
      <br /><br/>
      <span>Please wait until admin (Josh) approves your account</span> 
      <br />
      <span>You may receive an email when approved</span>
    </>
  );
}