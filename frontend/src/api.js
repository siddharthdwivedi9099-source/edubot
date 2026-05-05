// EduBot API client — RBAC-aware, JWT bearer tokens.
// Attaches Authorization header from localStorage on every request.
// Auto-redirects to login on 401.

const BASE = import.meta.env.VITE_API_BASE_URL || "/api";
const TOKEN_KEY = "edubot_token";
const USER_KEY = "edubot_user";

export const auth = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  getUser: () => {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  },
  setSession: (token, user) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clearSession: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
  isAuthed: () => !!localStorage.getItem(TOKEN_KEY),
};

async function jsonFetch(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const tok = auth.getToken();
  if (tok) headers.Authorization = `Bearer ${tok}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    auth.clearSession();
    if (window.location.pathname !== "/" && !window.location.hash.includes("login")) {
      window.location.reload();
    }
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.message || JSON.stringify(body);
    } catch {/* ignore */}
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json();
}

export const api = {
  // ── Auth ────────────────────────────────────────────────
  login: async (username, password) => {
    const res = await jsonFetch("/auth/login-json", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    auth.setSession(res.access_token, res.user);
    return res;
  },
  me: () => jsonFetch("/auth/me"),
  logout: async () => {
    try { await jsonFetch("/auth/logout", { method: "POST" }); } catch {/* ignore */}
    auth.clearSession();
  },

  // ── Health ──────────────────────────────────────────────
  health: () => jsonFetch("/health"),

  // ── Chat ────────────────────────────────────────────────
  chat: ({ messages, useRag = true, useErp = true, useWeb = false, sessionId }) =>
    jsonFetch("/chat", {
      method: "POST",
      body: JSON.stringify({
        messages,
        use_rag: useRag,
        use_erp: useErp,
        use_web: useWeb,
        session_id: sessionId,
      }),
    }),

  // ── KB ──────────────────────────────────────────────────
  kbCount: () => jsonFetch("/kb/count"),
  kbSearch: ({ query, k = 6 }) =>
    jsonFetch("/kb/search", {
      method: "POST",
      body: JSON.stringify({ query, k }),
    }),

  // ── ERP ─────────────────────────────────────────────────
  erpHealth: () => jsonFetch("/erp/health"),
  erpQuery: (query) =>
    jsonFetch("/erp/query", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),
};
