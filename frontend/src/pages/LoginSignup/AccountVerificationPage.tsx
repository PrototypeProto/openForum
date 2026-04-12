import { useEffect, useState } from "react";

export default function AccountVerificationPage() {
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("temp_user");
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        setUsername(parsed.username ?? null);
      } catch {
        // Malformed entry — ignore
      }
      // Clear immediately so sensitive data doesn't linger
      localStorage.removeItem("temp_user");
    }
  }, []);

  return (
    <>
      <h1>Successfully signed up!</h1>
      {username && <span>Account "{username}" has been created.</span>}
      <br />
      <br />
      <span>Please wait until the admin approves your account.</span>
      <br />
      <span>You may receive an email when approved.</span>
    </>
  );
}
