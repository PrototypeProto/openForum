import "./index.css";
import { Route, Routes } from "react-router-dom";
import HomePage from "./pages/Home/HomePage";
import LoginPage from "./pages/Login-Signup/LoginPage";
import ProfilePage from "./pages/Profile/ProfilePage";
import ErrorPage from "./pages/Error/ErrorPage";
import LogoutPage from "./pages/Logout/Logout";
import PortfolioPage from "./pages/Portfolio/PortfolioPage";
import ForumPage from "./pages/Forum/ForumPage";
import MediaPage from "./pages/Media/MediaPage";
import FileSharePage from "./pages/FileShare/FileSharePage";
import AboutPage from "./pages/About/AboutPage";
import AccountVerificationPage from "./pages/Login-Signup/AccountVerificationPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/error" element={<ErrorPage />} />
      <Route path="/logged-out" element={<LogoutPage />} />
      <Route path="/portfolio" element={<PortfolioPage />} />
      <Route path="/forum" element={<ForumPage />} />
      <Route path="/media" element={<MediaPage />} />
      <Route path="/file-share" element={<FileSharePage />} />
      <Route path="/account-pending-approval" element={<AccountVerificationPage />} />
    </Routes>
  );
}
