import { useEffect, useState } from "react";
import { api, auth } from "./api.js";
import LoginPage from "./LoginPage.jsx";
import Sidebar from "./Sidebar.jsx";
import Dashboard from "./Dashboard.jsx";
import ChatPanel from "./ChatPanel.jsx";

const ROLE_LABEL = {
  student: "Student",
  parent: "Parent",
  teacher: "Teacher",
  principal: "Principal",
  admin: "Admin",
  super_admin: "Group Super-Admin",
};

const ROLE_GREETING = {
  student: "Track your studies",
  parent: "Stay close to your child's journey",
  teacher: "Run your classroom",
  principal: "See your school clearly",
  admin: "Operations at a glance",
  super_admin: "Group-wide oversight",
};

export default function App() {
  const [user, setUser] = useState(auth.getUser());
  const [view, setView] = useState("dashboard");
  const [seedQuestion, setSeedQuestion] = useState(null);

  useEffect(() => {
    if (user?.role) document.body.dataset.role = user.role;
    else delete document.body.dataset.role;
  }, [user]);

  // Detect token expiry / 401 elsewhere; clear local state if storage cleared
  useEffect(() => {
    if (!user) return;
    const id = setInterval(() => {
      if (!auth.isAuthed()) setUser(null);
    }, 30000);
    return () => clearInterval(id);
  }, [user]);

  function onLoggedIn(u) {
    setUser(u);
    setView("dashboard");
  }

  async function handleLogout() {
    await api.logout();
    setUser(null);
  }

  function handleAskQuestion(q) {
    setSeedQuestion({ q, n: Date.now() });
    setView("chat");
  }

  if (!user) return <LoginPage onLoggedIn={onLoggedIn} />;

  return (
    <div className="app-shell">
      <Sidebar
        user={user}
        view={view}
        onView={setView}
        onLogout={handleLogout}
      />
      <main className="main">
        <div className="topbar">
          <div className="breadcrumb">
            <strong>{view === "dashboard" ? "Home" : "Ask EduBot"}</strong>
            <span style={{ color: "var(--ink-mute)" }}>
              · {ROLE_GREETING[user.role]}
            </span>
          </div>
          <div className="topbar-actions">
            <span className="pill">🏫 {user.school_id}</span>
            <span className="pill role">{ROLE_LABEL[user.role]}</span>
          </div>
        </div>
        <div className="content">
          {view === "dashboard" && (
            <Dashboard user={user} onAskQuestion={handleAskQuestion} />
          )}
          {view === "chat" && (
            <ChatPanel user={user} seedQuestion={seedQuestion?.q} seedKey={seedQuestion?.n} />
          )}
        </div>
      </main>
    </div>
  );
}
