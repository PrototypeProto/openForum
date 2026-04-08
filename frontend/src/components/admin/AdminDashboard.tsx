import { useState, useEffect } from "react";
import { useAdmin } from "../../hooks/useAdmin";
import { useAuthContext } from "../../context/AuthContext";
import { getUserStats } from "../../services/admin/adminService";
import type { UserRead, PendingUserRead, UserStats } from "../../types/adminTypes";
import type { Role } from "../../types/userTypes";
import "./css/adminDashboard.css";

type ViewSelection = "approval" | "users" | null;

// ── Pending user row ────────────────────────────────────────
function PendingRow({
  user,
  onApprove,
  onReject,
}: {
  user: PendingUserRead;
  onApprove: (u: string) => void;
  onReject: (u: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="admin-user-row">
      <div className="admin-user-row__main" onClick={() => setExpanded((p) => !p)}>
        <span className="admin-user-row__name">{user.username}</span>
        {user.nickname && (
          <span className="admin-user-row__nick">({user.nickname})</span>
        )}
        <span className="admin-user-row__date">{user.join_date}</span>
        <div className="admin-user-row__actions" onClick={(e) => e.stopPropagation()}>
          <button
            className="admin-action-btn admin-action-btn--approve"
            onClick={() => onApprove(user.username)}
          >
            approve
          </button>
          <button
            className="admin-action-btn admin-action-btn--reject"
            onClick={() => onReject(user.username)}
          >
            reject
          </button>
        </div>
      </div>
      {expanded && (
        <div className="admin-user-row__detail">
          {user.email && <span>email: {user.email}</span>}
          <span>request: {user.request ?? "—"}</span>
        </div>
      )}
    </div>
  );
}

// ── Verified user row ───────────────────────────────────────
const ROLES: Role[] = ["user", "vip", "admin"];

const ROLE_COLORS: Record<Role, string> = {
  admin: "#c9b99a",
  vip:   "#9ab8c9",
  user:  "var(--text-muted)",
};

function UserRow({
  user,
  onChangeRole,
}: {
  user: UserRead;
  onChangeRole: (username: string, role: Role) => void;
}) {
  return (
    <div className="admin-user-row">
      <div className="admin-user-row__main">
        <span className="admin-user-row__name">{user.username}</span>
        {user.nickname && (
          <span className="admin-user-row__nick">({user.nickname})</span>
        )}
        <span className={`admin-role-badge admin-role-badge--${user.role}`}>
          {user.role}
        </span>
        <div className="admin-user-row__actions">
          <select
            className="admin-role-select"
            value={user.role}
            style={{ color: ROLE_COLORS[user.role as Role] ?? "var(--text-muted)", borderColor: ROLE_COLORS[user.role as Role] ?? "var(--border)" }}
            onChange={(e) => onChangeRole(user.username, e.target.value as Role)}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}

// ── Main dashboard ──────────────────────────────────────────
export default function AdminDashboard() {
  const [currentView, setCurrentView] = useState<ViewSelection>(null);
  const [stats, setStats] = useState<UserStats | null>(null);
  const { authData } = useAuthContext();
  const {
    users,
    pendingUsers,
    usersLoading,
    pendingLoading,
    error,
    approve,
    reject,
    changeRole,
    actionError,
    actionSuccess,
  } = useAdmin(authData?.username ?? "");

  useEffect(() => {
    getUserStats().then((res) => {
      if (res.ok && res.data) setStats(res.data);
    });
  }, []);

  const toggle = (view: ViewSelection) =>
    setCurrentView((prev) => (prev === view ? null : view));

  return (
    <div className="admin-panel">

      {/* stats row */}
      <div className="site-stats">
        <div className="count-stat">
          <span className="count-stat__label">Users</span>
          <span className="count-stat__value">{stats ? String(stats.user) : "—"}</span>
        </div>
        <div className="count-stat">
          <span className="count-stat__label">VIP</span>
          <span className="count-stat__value">{stats ? String(stats.vip) : "—"}</span>
        </div>
        <div className="count-stat">
          <span className="count-stat__label">Admins</span>
          <span className="count-stat__value">{stats ? String(stats.admin) : "—"}</span>
        </div>
        <div className="count-stat--divider" />
        <div className="count-stat">
          <span className="count-stat__label">Pending</span>
          <span className="count-stat__value">
            {pendingLoading ? "—" : pendingUsers.length}
          </span>
        </div>
      </div>

      {/* global messages */}
      {error && <p className="admin-msg admin-msg--error">{error}</p>}
      {actionError && <p className="admin-msg admin-msg--error">{actionError}</p>}
      {actionSuccess && <p className="admin-msg admin-msg--success">{actionSuccess}</p>}

      {/* manage users section */}
      <div className="admin-section">
        <div className="admin-switch-bar">
          <span className="admin-switch-bar__label">Manage Users</span>
          <div className="admin-switch">
            <button
              className={`admin-switch__btn${currentView === "approval" ? " admin-switch__btn--active" : ""}`}
              onClick={() => toggle("approval")}
            >
              Pending ({pendingLoading ? "…" : pendingUsers.length})
            </button>
            <button
              className={`admin-switch__btn${currentView === "users" ? " admin-switch__btn--active" : ""}`}
              onClick={() => toggle("users")}
            >
              All Users ({usersLoading ? "…" : users.length})
            </button>
          </div>
        </div>

        {currentView && (
          <div className="admin-view" key={currentView}>

            {currentView === "approval" && (
              <>
                {pendingLoading ? (
                  <p className="admin-placeholder">Loading…</p>
                ) : pendingUsers.length === 0 ? (
                  <p className="admin-placeholder">No pending users.</p>
                ) : (
                  <div className="admin-user-list">
                    {pendingUsers.map((u) => (
                      <PendingRow
                        key={u.user_id}
                        user={u}
                        onApprove={approve}
                        onReject={reject}
                      />
                    ))}
                  </div>
                )}
              </>
            )}

            {currentView === "users" && (
              <>
                {usersLoading ? (
                  <p className="admin-placeholder">Loading…</p>
                ) : users.length === 0 ? (
                  <p className="admin-placeholder">No users yet.</p>
                ) : (
                  <div className="admin-user-list">
                    {users.map((u) => (
                      <UserRow key={u.user_id} user={u} onChangeRole={changeRole} />
                    ))}
                  </div>
                )}
              </>
            )}

          </div>
        )}
      </div>
    </div>
  );
}