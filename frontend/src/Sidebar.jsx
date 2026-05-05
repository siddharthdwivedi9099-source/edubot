const NAV_ITEMS = [
  { id: "dashboard", icon: "🏠", label: "Home" },
  { id: "chat",      icon: "💬", label: "Ask EduBot" },
];

function initials(name = "") {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() || "")
    .join("") || "?";
}

const ROLE_LABEL = {
  student: "Student",
  parent: "Parent",
  teacher: "Teacher",
  principal: "Principal",
  admin: "Admin",
  super_admin: "Super Admin",
};

export default function Sidebar({ user, view, onView, onLogout }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-brand-mark">E</span>
        <span className="sidebar-brand-name">EduBot</span>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section-title">Navigation</div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map((it) => (
            <button
              key={it.id}
              className={`sidebar-link ${view === it.id ? "active" : ""}`}
              onClick={() => onView(it.id)}
            >
              <span className="icon">{it.icon}</span>
              <span>{it.label}</span>
            </button>
          ))}
        </nav>
      </div>

      <div className="sidebar-user">
        <div className="user-card">
          <div className="user-avatar">{initials(user.full_name)}</div>
          <div style={{minWidth: 0}}>
            <div className="user-name">{user.full_name || user.user_id}</div>
            <div className="user-role">{ROLE_LABEL[user.role]}</div>
          </div>
        </div>
        <button className="btn-logout" onClick={onLogout}>
          Sign out
        </button>
      </div>
    </aside>
  );
}
