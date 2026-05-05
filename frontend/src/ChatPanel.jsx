import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";

const ROLE_GREETING = {
  student: "your studies",
  parent: "your child's school life",
  teacher: "your classroom",
  principal: "your school",
  admin: "operations",
  super_admin: "the entire group",
};

const ROLE_SUGGESTIONS = {
  student: [
    "📅 Show my attendance for this term.",
    "📝 List my pending assignments.",
    "📊 What are my marks in the latest exam?",
  ],
  parent: [
    "💸 What is my child's current fee status?",
    "📅 Show my child's attendance this month.",
    "🎓 Show the latest progress report.",
  ],
  teacher: [
    "🎯 Show today's attendance for my classes.",
    "📝 Which assignments do I still need to grade?",
    "⚠️ Which students in my class are at academic risk?",
  ],
  principal: [
    "📊 Show this term's class-wise performance.",
    "💰 Show fee collection status across the school.",
    "👩‍🏫 Show teacher performance ratings for my school.",
  ],
  admin: [
    "🚪 How many new admissions this academic year?",
    "💰 Show today's fee collection summary.",
    "📋 Who are the fee defaulters this term?",
  ],
  super_admin: [
    "🌐 Show enrolment by school for the group.",
    "📊 Compare academic performance across the schools.",
    "💰 Show fee collection rate by school.",
  ],
};

export default function ChatPanel({ user, seedQuestion, seedKey }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const streamRef = useRef(null);
  const composerRef = useRef(null);

  // Seed a question from Dashboard tile click
  useEffect(() => {
    if (seedQuestion) {
      send(seedQuestion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seedKey]);

  // Auto-scroll to bottom on new message
  useEffect(() => {
    streamRef.current?.scrollTo({
      top: streamRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  async function send(text) {
    const q = (text ?? input).trim();
    if (!q || loading) return;

    const next = [...messages, { role: "user", content: q }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const res = await api.chat({
        messages: next.map((m) => ({ role: m.role, content: m.content })),
        useRag: true,
        useErp: true,
      });
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: res.content,
          agent: res.agent,
          sources: res.sources || [],
          blocked: res.blocked,
          latency_ms: res.latency_ms,
        },
      ]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Sorry — something went wrong. ${err.message}`,
          agent: "Error",
          sources: [],
          blocked: true,
        },
      ]);
    } finally {
      setLoading(false);
      // refocus composer
      setTimeout(() => composerRef.current?.focus(), 0);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  const suggestions = ROLE_SUGGESTIONS[user.role] || ROLE_SUGGESTIONS.student;

  return (
    <div className="chat-shell">
      <div className="chat-stream" ref={streamRef}>
        {messages.length === 0 && !loading ? (
          <div className="chat-empty">
            <div className="chat-empty-mark">E</div>
            <h2>Ask EduBot</h2>
            <p>
              Ask about {ROLE_GREETING[user.role] || "school"} —
              EduBot pulls answers from the ERP, the school knowledge base,
              and the web. Your role is enforced on every answer.
            </p>
            <div className="suggested-questions">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  className="suggested-q"
                  onClick={() => send(s.replace(/^[^\s]+\s/, ""))}
                >
                  <span className="q-eyebrow">Try asking</span>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="bubble-row user">
                <div className="bubble user">{m.content}</div>
              </div>
            ) : (
              <div key={i} className="bubble-row assistant">
                <div className={`bubble assistant ${m.blocked ? "blocked" : ""}`}>
                  <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
                  {m.sources?.length > 0 && (
                    <div className="sources">
                      {m.sources.map((s, j) => (
                        <span key={j} className={`source-chip ${s.type}`}>
                          {s.type === "erp" && "📊 "}
                          {s.type === "kba" && "📚 "}
                          {s.type === "web" && "🌐 "}
                          {s.type === "system" && "⚙️ "}
                          {s.title}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="assistant-meta">
                    <span className="agent">{m.agent}</span>
                    {typeof m.latency_ms === "number" &&
                      ` · ${(m.latency_ms / 1000).toFixed(1)}s`}
                  </div>
                </div>
              </div>
            )
          )
        )}

        {loading && (
          <div className="bubble-row assistant">
            <div className="bubble assistant">
              <div className="thinking">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}
      </div>

      <div>
        <div className="composer">
          <textarea
            ref={composerRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={`Ask anything about ${ROLE_GREETING[user.role] || "school"}…`}
            rows={1}
            autoFocus
          />
          <button
            className="composer-send"
            onClick={() => send()}
            disabled={loading || !input.trim()}
            aria-label="Send"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </div>
        <div className="composer-hint">
          Press <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for new line
        </div>
      </div>
    </div>
  );
}
