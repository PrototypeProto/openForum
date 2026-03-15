import "./HomePage.css";
import { Navbar } from "../../components/Navbar";
import { useAuthContext } from "../../context/AuthContext";

export default function HomePage() {
  const { authData, getUsernameOrGuest } = useAuthContext();

  return (
    <div className="homepage">
      <Navbar username={authData?.username} />

      <main className="hero">
        <h1>
          Esteemed {getUsernameOrGuest()}!<br></br>
          Welcome to Josh's Den
        </h1>
        <p>Joshua's social network</p>

        {/* TODO: Primary CTA - wire up to your intended action */}
        <button className="cta-button">Get Started</button>
      </main>

      {/* TODO: Add more sections below (features, pricing, etc.) */}
    </div>
  );
}
