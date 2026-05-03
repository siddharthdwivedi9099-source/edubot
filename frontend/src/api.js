// Thin wrapper around the EduBot FastAPI backend.
// In dev (vite) we proxy /api → http://localhost:8000 (see vite.config.js).
// In prod (nginx) the same /api prefix is reverse-proxied to the backend.
// Override at build time with VITE_API_BASE_URL if needed.

const BASE = import.meta.env.VITE_API_BASE_URL || "/api";

async function jsonFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.message || JSON.stringify(body);
    } catch {
      /* not json */
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json();
}

export const api = {
  health: () => jsonFetch("/health"),

  chat: ({ persona, userId, messages, useRag = true, useErp = true, useWeb = false, sessionId }) =>
    jsonFetch("/chat", {
      method: "POST",
      body: JSON.stringify({
        persona,
        user_id: userId,
        messages,
        use_rag: useRag,
        use_erp: useErp,
        use_web: useWeb,
        session_id: sessionId,
      }),
    }),

  kbCount: () => jsonFetch("/kb/count"),
  kbSearch: ({ query, audience, k = 6 }) =>
    jsonFetch("/kb/search", {
      method: "POST",
      body: JSON.stringify({ query, audience, k }),
    }),

  erpHealth: () => jsonFetch("/erp/health"),
  erpSchema: () => jsonFetch("/erp/schema"),
  erpQuery: ({ question, persona, userContext }) =>
    jsonFetch("/erp/query", {
      method: "POST",
      body: JSON.stringify({
        question,
        persona,
        user_context: userContext,
      }),
    }),
};
