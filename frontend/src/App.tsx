import "./index.css";
import { Route, Routes } from "react-router-dom";
import HomePage from "./pages/Home/HomePage";
import LoginPage from "./pages/LoginSignup/LoginPage";
import ProfilePage from "./pages/Profile/ProfilePage";
import ErrorPage from "./pages/Error/ErrorPage";
import LogoutPage from "./pages/Logout/Logout";
import PortfolioPage from "./pages/Portfolio/PortfolioPage";
import ForumPage from "./pages/Forum/ForumPage";
import TopicPage from "./pages/Forum/TopicPage";
import ThreadPage from "./pages/Thread/ThreadPage";
import MediaPage from "./pages/Media/MediaPage";
import FileSharePage from "./pages/FileShare/FileSharePage";
import DownloadPage from "./pages/FileShare/DownloadPage";
import AboutPage from "./pages/About/AboutPage";
import AccountVerificationPage from "./pages/LoginSignup/AccountVerificationPage";
import { GuestRoute } from "./guards/GuestRoute";
import { ProtectedRoute } from "./guards/ProtectedRoute";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route
        path="/login"
        element={
          <GuestRoute>
            <LoginPage />
          </GuestRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        }
      />

      {/* <Route path="/admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} /> */}

      <Route path="/error" element={<ErrorPage />} />
      <Route path="/logged-out" element={<LogoutPage />} />
      <Route path="/portfolio" element={<PortfolioPage />} />
      <Route path="/forum" element={<ForumPage />} />
      <Route path="/forum/:topicName" element={<TopicPage />} />
      <Route path="/thread/:threadId" element={<ThreadPage />} />
      <Route path="/media" element={<MediaPage />} />
      <Route path="/file-share" element={<FileSharePage />} />
      <Route path="/file-share/download/:fileId" element={<DownloadPage />} />
      <Route
        path="/account-pending-approval"
        element={<AccountVerificationPage />}
      />
    </Routes>
  );
}