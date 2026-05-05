import { useState } from "react";
import { api } from "./api.js";

export default function LoginPage({ onLoggedIn }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.login(username.trim(), password);
      onLoggedIn(res.user);
    } catch (err) {
      setError(err.message || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function fillCredentials(u, p) {
    setUsername(u);
    setPassword(p);
  }

  return (
    <div className="login-shell">
      {/* ── Left: hero ─────────────────────────────────────── */}
      <aside className="login-hero">
        <div className="login-brand">
          <span className="login-brand-mark">E</span>
          <span>EduBot</span>
        </div>

        <div>
          <h1 className="login-headline">
            One assistant<br/>for the entire <em>school</em>.
          </h1>
          <p className="login-tagline">
            EduBot connects to your ERP, knowledge base, and the web — and
            answers each role with exactly the data they're allowed to see.
            Built for the entire school ecosystem.
          </p>

          <div className="login-stats">
            <div className="login-stat">
              <div className="num">20</div>
              <div className="label">Schools</div>
            </div>
            <div className="login-stat">
              <div className="num">10K</div>
              <div className="label">Students</div>
            </div>
            <div className="login-stat">
              <div className="num">6</div>
              <div className="label">Roles</div>
            </div>
          </div>
        </div>

        <div style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.12em",
          color: "rgba(244, 239, 230, 0.5)",
        }}>
          RBAC · CBSE · ERP-INTEGRATED · MOBILE-READY
        </div>
      </aside>

      {/* ── Right: form ────────────────────────────────────── */}
      <section className="login-form-wrap">
        <form className="login-form" onSubmit={handleSubmit}>
          <h1>Sign in</h1>
          <p className="lead">Use your school-issued credentials.</p>

          {error && <div className="login-error">{error}</div>}

          <div className="field">
            <label className="field-label" htmlFor="username">Username</label>
            <input
              id="username"
              className="field-input"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. principal1"
              autoComplete="username"
              required
            />
          </div>

          <div className="field">
            <label className="field-label" htmlFor="password">Password</label>
            <input
              id="password"
              className="field-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          </div>

          <button className="btn-primary" type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </button>

          <div className="demo-creds">
            <h4>Demo credentials</h4>
            <p style={{ color: "var(--ink-soft)", marginBottom: 10 }}>
              All passwords are <code>demo</code>. Click a row to autofill.
            </p>
            <ul>
              <li onClick={() => fillCredentials("superadmin", "demo")} style={{cursor:"pointer"}}>
                <code>superadmin</code> — group oversight (all 20 schools)
              </li>
              <li onClick={() => fillCredentials("principal1", "demo")} style={{cursor:"pointer"}}>
                <code>principal1</code> — Principal of School 1
              </li>
              <li onClick={() => fillCredentials("teacher_tch00001", "demo")} style={{cursor:"pointer"}}>
                <code>teacher_tch00001</code> — A teacher
              </li>
              <li onClick={() => fillCredentials("parent_par000001", "demo")} style={{cursor:"pointer"}}>
                <code>parent_par000001</code> — A parent
              </li>
              <li onClick={() => fillCredentials("student_stu000001", "demo")} style={{cursor:"pointer"}}>
                <code>student_stu000001</code> — A student
              </li>
              <li onClick={() => fillCredentials("admin_adm00001", "demo")} style={{cursor:"pointer"}}>
                <code>admin_adm00001</code> — School admin (registrar)
              </li>
            </ul>
          </div>
        </form>
      </section>
    </div>
  );
}
