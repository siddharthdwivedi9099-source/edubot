import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api.js";

/* ============================================================
   PERSONAS — system prompts live on the backend; the UI just
   carries display data and suggested starter prompts.
   ============================================================ */
const PERSONAS = [
  {
    id: "student",
    name: "Student",
    role: "Curious learner",
    accent: "var(--acc-student)",
    avatar: "ST",
    intro: (
      <>
        Ask about <em>your timetable</em>, <em>this week's homework</em>, or anything you wish you'd
        understood the first time.
      </>
    ),
    suggestions: [
      { q: "Explain", body: "photosynthesis like I'm in grade 6, with a quick analogy." },
      { q: "What's", body: "my attendance percentage this term?" },
      { q: "When", body: "is the next mathematics unit test, and what's covered?" },
      { q: "Help me", body: "plan a 5-day study schedule for half-yearly exams." },
    ],
  },
  {
    id: "teacher",
    name: "Teacher",
    role: "Classroom partner",
    accent: "var(--acc-teacher)",
    avatar: "TR",
    intro: (
      <>
        Pull up <em>class rosters</em>, draft <em>parent communication</em>, or generate
        differentiated lesson material — grounded in school policy.
      </>
    ),
    suggestions: [
      { q: "Show me", body: "students with attendance below 75% in Grade 8-A." },
      { q: "Draft", body: "a polite parent email about a missed assignment." },
      { q: "Generate", body: "5 MCQs and 2 short-answer questions on the water cycle." },
      { q: "Summarise", body: "the school's late-submission policy for my reference." },
    ],
  },
  {
    id: "parent",
    name: "Parent",
    role: "Family liaison",
    accent: "var(--acc-parent)",
    avatar: "PA",
    intro: (
      <>
        Track <em>your child's progress</em>, check <em>fee status</em>, and stay in step with the
        school calendar — without phone-tag.
      </>
    ),
    suggestions: [
      { q: "What is", body: "my child's attendance and last term result?" },
      { q: "When is", body: "the next parent-teacher meeting?" },
      { q: "How do", body: "I apply for an extended-leave permission?" },
      { q: "Are there", body: "any pending fees on my account?" },
    ],
  },
  {
    id: "admin",
    name: "Administrator",
    role: "Operations & policy",
    accent: "var(--acc-admin)",
    avatar: "AD",
    intro: (
      <>
        Run <em>school-wide reports</em>, audit <em>policy questions</em>, and surface what needs
        attention this week.
      </>
    ),
    suggestions: [
      { q: "List", body: "classes with attendance below 80% this month." },
      { q: "Total", body: "fees collected vs pending for the current quarter." },
      { q: "Show", body: "transport routes and how many students use each." },
      { q: "Audit", body: "data-privacy policy gaps for parent communication." },
    ],
  },
];

const SOURCE_ICON = {
  kba: "📚",
  erp: "🗂",
  web: "🌐",
  system: "⚙︎",
};

/* ============================================================
   Web Speech API hook — graceful fallback if unavailable.
   ============================================================ */
function useVoiceInput() {
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(false);
  const recognitionRef = useRef(null);

  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    setSupported(true);
    const rec = new SR();
    rec.continuous = false;
    rec.interimResults = false;
    rec.lang = "en-IN"; // Indian English; falls back fine for other accents
    recognitionRef.current = rec;
  }, []);

  const start = (onResult) => {
    const rec = recognitionRef.current;
    if (!rec) return;
    rec.onresult = (e) => onResult(e.results[0][0].transcript);
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    setListening(true);
    rec.start();
  };

  const stop = () => {
    const rec = recognitionRef.current;
    if (rec && listening) rec.stop();
  };

  return { supported, listening, start, stop };
}

function speak(text) {
  if (!window.speechSynthesis) return;
  // Strip markdown fences/sql blocks for nicer audio
  const clean = text.replace(/```[\s\S]*?```/g, " ").replace(/[#*_`>]/g, "");
  const utter = new SpeechSynthesisUtterance(clean.slice(0, 600));
  utter.rate = 1.02;
  utter.pitch = 1;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utter);
}

/* ============================================================
   Components
   ============================================================ */
function MessageBubble({ message, persona, onSpeak }) {
  const isUser = message.role === "user";
  const accent = persona.accent;
  return (
    <div className={`msg ${isUser ? "user" : "bot"}`}>
      <div className="avatar" style={isUser ? { background: accent, color: "#fff", borderColor: accent } : undefined}>
        {isUser ? persona.avatar : "Eb"}
      </div>
      <div className="bubble" style={!isUser && message.agent ? { "--accent": accent } : undefined}>
        {!isUser && message.agent && (
          <div className="agent-tag" style={{ background: accent }}>
            {message.agent}
          </div>
        )}
        <div>{message.content}</div>

        {message.sql && (
          <pre className="sql-block">
            <span style={{ color: "var(--ink-mute)" }}>-- generated SQL --</span>
            {"\n"}
            {message.sql}
          </pre>
        )}

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="sources">
            {message.sources.map((s, i) => (
              <span key={i} className={`source ${s.type}`} title={s.text || s.title || ""}>
                {SOURCE_ICON[s.type] || "•"} {s.title || s.type.toUpperCase()}
              </span>
            ))}
          </div>
        )}

        {!isUser && message.content && !message.pending && (
          <button
            className="icon-btn"
            style={{ float: "right", marginTop: 6 }}
            onClick={() => onSpeak(message.content)}
            aria-label="Read aloud"
            title="Read aloud"
          >
            🔊
          </button>
        )}
      </div>
    </div>
  );
}

function TypingBubble({ persona }) {
  return (
    <div className="msg bot">
      <div className="avatar">Eb</div>
      <div className="bubble" style={{ "--accent": persona.accent }}>
        <div className="typing">
          <span /> <span /> <span />
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Right panel — Knowledge Base & ERP schema
   ============================================================ */
function RightPanel({ persona }) {
  const [tab, setTab] = useState("kb");
  const [kbCount, setKbCount] = useState(null);
  const [erpInfo, setErpInfo] = useState(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [schema, setSchema] = useState(null);

  useEffect(() => {
    api.kbCount().then((r) => setKbCount(r.count)).catch(() => setKbCount(0));
    api.erpHealth().then(setErpInfo).catch(() => setErpInfo({ ok: false }));
  }, []);

  useEffect(() => {
    if (tab === "erp" && !schema) {
      api.erpSchema().then(setSchema).catch(() => setSchema({ tables: [] }));
    }
  }, [tab, schema]);

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const r = await api.kbSearch({ query, audience: persona.id, k: 6 });
      setResults(r.results || []);
    } catch (e) {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  return (
    <aside className="panel-right">
      <div className="tab-row">
        <button className={`tab ${tab === "kb" ? "active" : ""}`} onClick={() => setTab("kb")}>
          Knowledge
        </button>
        <button className={`tab ${tab === "erp" ? "active" : ""}`} onClick={() => setTab("erp")}>
          School Data
        </button>
      </div>

      {tab === "kb" && (
        <div className="right-section">
          <div className="stat-block">
            <div className="stat">
              <div className="stat-num">{kbCount ?? "—"}</div>
              <div className="stat-label">KB chunks indexed</div>
            </div>
            <div className="stat">
              <div className="stat-num">RAG</div>
              <div className="stat-label">Grounded retrieval</div>
            </div>
          </div>

          <div className="kb-search">
            <input
              placeholder="Search policies, FAQs, guides…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
            />
            <button onClick={search}>Go</button>
          </div>

          {searching && <div className="empty-state">Searching…</div>}
          {!searching && results.length === 0 && (
            <div className="empty-state">
              {kbCount === 0
                ? "Knowledge base not yet ingested. Run scripts/ingest_kb.py to populate."
                : "Search to surface policies, FAQs and how-to articles."}
            </div>
          )}
          {results.map((r, i) => (
            <div key={i} className="kb-card">
              <div className="kb-card-meta">
                <span>{r.category || "general"}</span>
                <span>•</span>
                <span>{r.audience?.join("/") || "all"}</span>
              </div>
              <div className="kb-card-title">{r.title}</div>
              <div className="kb-card-snippet">{r.snippet || r.content}</div>
            </div>
          ))}
        </div>
      )}

      {tab === "erp" && (
        <div className="right-section">
          <div className="stat-block">
            <div className="stat">
              <div className="stat-num">{erpInfo?.ok ? "✓" : "—"}</div>
              <div className="stat-label">{erpInfo?.ok ? "ERP connected" : "ERP offline"}</div>
            </div>
            <div className="stat">
              <div className="stat-num">{erpInfo?.read_only ? "RO" : "RW"}</div>
              <div className="stat-label">Access mode</div>
            </div>
          </div>

          <div className="section-label" style={{ padding: "16px 0 8px" }}>
            Tables exposed
          </div>
          {!schema && <div className="empty-state">Loading schema…</div>}
          {schema?.tables?.length === 0 && (
            <div className="empty-state">
              No ERP connected. Set <code>ERP_DB_URL</code> in your <code>.env</code>.
            </div>
          )}
          {schema?.tables?.map((t) => (
            <div key={t.name} className="schema-card">
              <span className="table-name">{t.name}</span>
              <span style={{ color: "var(--ink-mute)" }}> ({t.row_count ?? "?"} rows)</span>
              {"\n"}
              {t.columns?.slice(0, 8).join(", ")}
              {t.columns && t.columns.length > 8 && "…"}
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}

/* ============================================================
   App
   ============================================================ */
export default function App() {
  const [personaId, setPersonaId] = useState("student");
  const persona = useMemo(() => PERSONAS.find((p) => p.id === personaId), [personaId]);

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  const [health, setHealth] = useState(null);
  const [useRag, setUseRag] = useState(true);
  const [useErp, setUseErp] = useState(true);
  const [useWeb, setUseWeb] = useState(false);

  const sessionId = useMemo(
    () => `sess-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    [personaId] // new session per persona switch
  );
  const conversationRef = useRef(null);
  const voice = useVoiceInput();

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth({ status: "offline" }));
  }, []);

  // reset messages when persona changes
  useEffect(() => {
    setMessages([]);
    setInput("");
    setError(null);
  }, [personaId]);

  // autoscroll
  useEffect(() => {
    const el = conversationRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, pending]);

  const send = async (raw) => {
    const text = (raw ?? input).trim();
    if (!text || pending) return;
    setError(null);
    setInput("");

    const newUser = { role: "user", content: text };
    const history = [...messages, newUser];
    setMessages(history);
    setPending(true);

    try {
      const res = await api.chat({
        persona: personaId,
        userId: `${personaId}-demo`,
        messages: history.map(({ role, content }) => ({ role, content })),
        useRag,
        useErp,
        useWeb,
        sessionId,
      });
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: res.message,
          sources: res.sources || [],
          agent: res.agent,
          sql: res.sql,
        },
      ]);
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(false);
    }
  };

  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="app" style={{ "--accent": persona.accent }}>
      <header className="masthead">
        <div className="brand">
          <span className="brand-mark">
            EduBot<span className="dot">.</span>
          </span>
          <span className="brand-tag">A grounded assistant for schools</span>
        </div>
        <div className="health">
          <span>
            <span className={`dot-led ${health?.status === "ok" ? "ok" : health?.status === "offline" ? "bad" : ""}`} />
            backend {health?.status || "…"}
          </span>
          <span>llm: {health?.llm_provider || "…"}</span>
          <span>kb: {health?.kb_chunks ?? "…"}</span>
        </div>
      </header>

      <div className="layout">
        {/* LEFT — personas + suggestions */}
        <aside className="panel-left">
          <div className="section-label">Speak as</div>
          <div className="persona-list">
            {PERSONAS.map((p) => (
              <button
                key={p.id}
                className={`persona ${p.id === personaId ? "active" : ""}`}
                onClick={() => setPersonaId(p.id)}
                style={{ "--accent": p.accent }}
              >
                <span className="persona-stripe" />
                <span className="persona-meta">
                  <span className="persona-name">{p.name}</span>
                  <span className="persona-role">{p.role}</span>
                </span>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--ink-mute)" }}>
                  {p.id === personaId ? "● ACTIVE" : ""}
                </span>
              </button>
            ))}
          </div>

          <div className="section-label">Try asking</div>
          <div className="suggestions">
            {persona.suggestions.map((s, i) => (
              <button
                key={i}
                className="suggestion"
                onClick={() => send(`${s.q} ${s.body}`)}
                style={{ "--accent": persona.accent }}
              >
                <span className="suggestion-q">{s.q}</span>
                {s.body}
              </button>
            ))}
          </div>
        </aside>

        {/* CENTER — conversation */}
        <main className="panel-main">
          <div className="persona-banner">
            <div className="persona-headline">
              <span className="persona-headline-name" style={{ color: persona.accent }}>
                {persona.name}
              </span>
              <span className="persona-headline-context">{persona.role.toLowerCase()}</span>
            </div>
            <div className="toggles">
              <button className={`toggle ${useRag ? "on" : ""}`} onClick={() => setUseRag(!useRag)}>
                KB
              </button>
              <button className={`toggle ${useErp ? "on" : ""}`} onClick={() => setUseErp(!useErp)}>
                ERP
              </button>
              <button className={`toggle ${useWeb ? "on" : ""}`} onClick={() => setUseWeb(!useWeb)}>
                Web
              </button>
            </div>
          </div>

          {error && (
            <div className="error-pill">
              <span>⚠ {error}</span>
              <button onClick={() => setError(null)}>Dismiss</button>
            </div>
          )}

          <div className="conversation" ref={conversationRef}>
            {messages.length === 0 && <div className="intro">{persona.intro}</div>}

            {messages.map((m, i) => (
              <MessageBubble key={i} message={m} persona={persona} onSpeak={speak} />
            ))}

            {pending && <TypingBubble persona={persona} />}
          </div>

          <div className="composer">
            <div className="composer-row">
              <textarea
                placeholder={`Ask ${persona.name.toLowerCase()} something…`}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKey}
                rows={1}
              />
              {voice.supported && (
                <button
                  className={`icon-btn ${voice.listening ? "recording" : ""}`}
                  onClick={() =>
                    voice.listening
                      ? voice.stop()
                      : voice.start((t) => setInput((prev) => (prev ? `${prev} ${t}` : t)))
                  }
                  title={voice.listening ? "Stop" : "Voice input"}
                  aria-label="Voice input"
                >
                  {voice.listening ? "■" : "🎙"}
                </button>
              )}
              <button className="send-btn" onClick={() => send()} disabled={pending || !input.trim()}>
                Send →
              </button>
            </div>
            <div className="composer-hint">
              <span>
                <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for newline
              </span>
              <span>session: {sessionId.slice(0, 16)}…</span>
            </div>
          </div>
        </main>

        <RightPanel persona={persona} />
      </div>

      <footer className="footer">
        <span>
          EduBot v1.0 · open source · self-hostable
        </span>
        <div className="footer-rules">
          <span>PII redaction</span>
          <span>Read-only ERP</span>
          <span>RAG-grounded answers</span>
          <span>Role guardrails</span>
        </div>
      </footer>
    </div>
  );
}
