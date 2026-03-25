import { useState } from "react";
import "./css/adminDashboard.css";

type ViewSelection = "approval" | "reports" | null;

export default function AdminDashboard() {
  const [currentView, setCurrentView] = useState<ViewSelection>(null);

  const toggle = (view: ViewSelection) => {
    setCurrentView((prev) => (prev === view ? null : view));
  };

  return (
    <div className="admin-panel">
      {/* ── stats row ── */}
      <div className="site-stats">
        <div className="count-stat">
          <span className="count-stat__label">Users</span>
          <span className="count-stat__value">—</span>
        </div>
        <div className="count-stat">
          <span className="count-stat__label">Admins</span>
          <span className="stat__value">—</span>
        </div>
        <div className="count-stat">
          <span className="count-stat__label">Pending Users</span>
          <span className="stat__value">—</span>
        </div>
      </div>

      {/* ── manage users ── */}
      <div className="admin-section">
        {/* switch bar */}
        <div className="admin-switch-bar">
          <span className="admin-switch-bar__label">Manage Users</span>
          <div className="admin-switch">
            <button
              className={`admin-switch__btn ${currentView === "approval" ? "admin-switch__btn--active" : ""}`}
              onClick={() => toggle("approval")}
            >
              Approve Pending
            </button>
            <button
              className={`admin-switch__btn ${currentView === "reports" ? "admin-switch__btn--active" : ""}`}
              onClick={() => toggle("reports")}
            >
              View Reports
            </button>
          </div>
        </div>

        {/* content panel */}
        {currentView && (
          <div className="admin-view" key={currentView}>
            {currentView === "approval" && (
              <p className="admin-placeholder">No pending users.</p>
            )}
            {currentView === "reports" && (
              <p className="admin-placeholder">No reports available.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
