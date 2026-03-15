import { Navbar } from "../../components/Navbar";
import { useAuthContext } from "../../context/AuthContext";

export default function ProfilePage() {
  const { authData, getUsernameOrGuest } = useAuthContext();

  if (!authData) {
    return (
      <div className="profile-notloggedin-page">
        <h1>You are not signed in.</h1>
        You are currently in {getUsernameOrGuest()} mode
      </div>
    );
  }

  return (
    <>
      <Navbar username={authData?.username} />
      <div className="profile-page">
        <h1>Successfully logged in!</h1>
        <span>Welcome {authData.username}</span>
        <br />
        <span>Your user id is: {authData.user_id}</span>
        <br />
        <span>
          You also go by:{" "}
          {authData?.nickname ?? "No nickname associated to this account"}
        </span>
        <br />
        <span>Your current privileges are {authData.role}</span>
        <br />
      </div>
    </>
  );
}
