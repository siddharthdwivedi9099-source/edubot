# EduBot — A grounded AI assistant for schools

> Voice-enabled, RAG-backed, ERP-aware conversational AI for **students, teachers, parents, and administrators** — self-hostable on a single laptop, scalable to the cloud, ready to plug into any SQL-based school ERP.

EduBot is an open, production-grade reference implementation of an AI assistant designed specifically for K-12 schools. It combines a **FastAPI backend**, a **LangChain RAG pipeline** over 1,100+ curated knowledge-base articles, a **read-only NL→SQL connector** to your existing school ERP, **WhatsApp** integration, and a **role-aware guardrail layer** — all behind a polished, persona-switching React UI.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              EduBot                                     │
│                                                                         │
│   Student     Teacher     Parent     Admin                              │
│      │           │           │          │                               │
│      ▼           ▼           ▼          ▼                               │
│   ┌───────────────────────────────────────────┐                         │
│   │  Web UI (React)  ·  WhatsApp  ·  Voice    │                         │
│   └────────────────────┬──────────────────────┘                         │
│                        │ HTTPS                                          │
│                        ▼                                                │
│   ┌───────────────────────────────────────────┐                         │
│   │  FastAPI  ──  Guardrails  ──  Router      │                         │
│   └─────┬───────────────┬─────────────┬───────┘                         │
│         │               │             │                                 │
│    ┌────▼─────┐   ┌─────▼────┐   ┌────▼─────┐                           │
│    │   RAG    │   │  ERP NL  │   │ Web/Tool │                           │
│    │ (Chroma) │   │ →SQL     │   │  Agent   │                           │
│    └────┬─────┘   └─────┬────┘   └────┬─────┘                           │
│         ▼               ▼             ▼                                 │
│    1,100+ KB        Any SQL ERP    LLM (Ollama /                        │
│    articles         (read-only)    OpenAI / Anthropic)                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## What's in the box

| Layer        | Tech                                                                                  |
| ------------ | ------------------------------------------------------------------------------------- |
| **Frontend** | React 18 + Vite, distinctive editorial design system, Web Speech API for voice I/O    |
| **Backend**  | FastAPI, async, Pydantic v2, slowapi rate-limiting, Loguru                            |
| **LLMs**     | **Ollama** (default, local) · **OpenAI** · **Anthropic** — plug-and-play via `.env`   |
| **RAG**      | LangChain + Chroma (embedded, no extra service) + sentence-transformers fallback      |
| **ERP**      | SQLAlchemy async — works with **SQLite, MySQL, PostgreSQL, MS SQL Server, MariaDB**   |
| **Channels** | Web UI · WhatsApp (Twilio) · Voice (Web Speech) · REST API                            |
| **Safety**   | Input/output guardrails, PII redaction, role-based scoping, off-topic filter, RO ERP  |
| **Deploy**   | Single-command `docker compose up`, or step-by-step bare-metal install                |

### What ships seeded

- **1,100 KB articles** — academic guides, school policies, FAQs, event templates, safety drills, holiday handbooks (Indian school context, but easily replaced)
- **Demo SQLite ERP** — 1,072 students · 40 teachers · 45,024 attendance rows · 17,433 exam results · 4,288 fee records · timetables · transport · library
- **4 personas** — student, teacher, parent, administrator, each with role-tuned system prompts and starter prompts

---

## Quick start

### 🔥 Option A — Docker (recommended, zero hassle)

The fastest way to see EduBot running with a local LLM, the demo ERP, and the seeded knowledge base.

```bash
# 1. Clone
git clone <your-repo-url> edubot && cd edubot

# 2. Provide environment defaults
cp backend/.env.example backend/.env

# 3. Stand it all up — pulls Ollama models on first run (~5–10 GB, one-time)
docker compose up --build

# 4. After the first build, ingest the KB into Chroma
docker compose exec backend python scripts/ingest_kb.py

# 5. Open the app
open http://localhost:8080
```

What you get on first launch:
- Frontend at `http://localhost:8080`
- Backend API at `http://localhost:8000` (Swagger at `/docs`)
- Ollama at `http://localhost:11434`

### 💻 Option B — Local install (no Docker)

Use this if you're a developer who wants live-reload, or you're deploying to bare metal.

#### Prerequisites
- Python 3.11+
- Node 20+
- (optional) [Ollama](https://ollama.com/download) — for the free, offline LLM path
- (optional) An OpenAI or Anthropic API key — if you'd rather use a hosted LLM

#### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # adjust if you want OpenAI/Anthropic

# If using Ollama (default), pull the models once:
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# Generate KB articles + demo ERP DB (already done if you cloned the repo)
python scripts/generate_kb.py
python scripts/seed_db.py

# Ingest the KB into Chroma (one-time, idempotent with --reset)
python scripts/ingest_kb.py

# Run the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
# opens http://localhost:5173 — proxies /api → http://localhost:8000
```

That's it. Open **http://localhost:5173** and chat.

---

## Switching to OpenAI or Anthropic (no Ollama)

Edit `backend/.env`:

```bash
# Pick one
LLM_PROVIDER=openai        # or 'anthropic' or 'ollama'

OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# OR
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_CHAT_MODEL=claude-sonnet-4-5
# Anthropic has no embeddings endpoint — EduBot auto-falls-back to a
# local sentence-transformers model so RAG still works.
```

Restart the backend; that's the whole change.

---

## Connecting your real school ERP

EduBot's ERP connector is **read-only by default** and works with any SQL database SQLAlchemy supports. Set the URL in `backend/.env`:

```bash
# SQLite (the default demo)
ERP_DB_URL=sqlite+aiosqlite:///./app/data/demo_school.db

# MySQL / MariaDB
ERP_DB_URL=mysql+asyncmy://readonly_user:pass@db.school.local:3306/school_erp

# PostgreSQL
ERP_DB_URL=postgresql+asyncpg://readonly:pass@db.school.local:5432/school_erp

# MS SQL Server
ERP_DB_URL=mssql+aioodbc://readonly:pass@db.school.local/school_erp?driver=ODBC+Driver+18+for+SQL+Server

ERP_READ_ONLY=true   # ← keep this on. Blocks DDL/DML at the SQL level.
```

The connector introspects your schema on startup, surfaces it to the LLM as context, and translates natural-language questions into safe `SELECT` statements. Every query is shown alongside the answer in the UI — full audit trail, no black box.

> **Tip**: Create a dedicated read-only DB user for EduBot. The application enforces read-only mode, but defence in depth is what makes admins sleep at night.

---

## WhatsApp integration

EduBot ships a Twilio-based WhatsApp webhook at `/whatsapp/inbound`.

1. Set up a [Twilio Sandbox for WhatsApp](https://www.twilio.com/docs/whatsapp/sandbox) (free for testing).
2. Set the webhook URL in your Twilio console to:
   ```
   https://your-domain.example.com/whatsapp/inbound
   ```
3. Add your credentials to `backend/.env`:
   ```bash
   TWILIO_ACCOUNT_SID=AC...
   TWILIO_AUTH_TOKEN=...
   TWILIO_FROM_NUMBER=whatsapp:+14155238886
   ```
4. Users prefix their first message with `[student]`, `[teacher]`, `[parent]`, or `[admin]` to set their persona. Default is `parent`.

---

## Guardrails — why every stakeholder is safe

EduBot has multiple layers of safety that **cannot be turned off** from the UI:

| Layer                        | What it does                                                                              |
| ---------------------------- | ----------------------------------------------------------------------------------------- |
| **Input length cap**         | Rejects oversized prompts (default 4 KB)                                                  |
| **Profanity filter**         | Strips abusive language in either direction                                               |
| **PII redaction**            | Scrubs phone, email, Aadhaar, PAN, card numbers from logs                                 |
| **Off-topic filter**         | Refuses non-school questions ("write me a poem about crypto") — keeps focus               |
| **Role guardrail**           | Students and parents cannot ask about *other* students/staff                              |
| **Read-only ERP**            | Blocks any SQL that isn't a `SELECT` even if the LLM tries                                |
| **RAG-grounded answers**     | KB-driven answers cite their sources; the LLM is told never to fabricate policy           |
| **Output post-check**        | Strips API-key-looking tokens or profanity that slipped through                           |
| **Rate limiting**            | Per-IP per-minute cap (default 30) via slowapi                                            |

See [`docs/GUARDRAILS.md`](docs/GUARDRAILS.md) for full details and tuning.

---

## Cloud deployment (online)

The short version: any platform that runs Docker or a Python web service will host EduBot. We've documented the most common paths:

- **Railway / Render / Fly.io** — one-click backend, free tier sufficient for a single school
- **Vercel / Netlify** — for the frontend (static), point `VITE_API_BASE_URL` at the backend
- **AWS / GCP / Azure** — production patterns with managed Postgres, secrets manager, and HTTPS

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for a step-by-step guide for each.

---

## Repository layout

```
edubot/
├── backend/                    FastAPI + RAG + ERP + WhatsApp
│   ├── app/
│   │   ├── api/                Route modules (chat, kb, erp, whatsapp)
│   │   ├── core/               agent, llm, rag, erp_connector, guardrails
│   │   ├── models/             Pydantic schemas
│   │   ├── data/               KB JSON + demo SQLite ERP (gitignored at runtime)
│   │   ├── config.py
│   │   └── main.py
│   ├── scripts/
│   │   ├── generate_kb.py      Produces 1,100+ articles
│   │   ├── seed_db.py          Builds the demo school SQLite DB
│   │   └── ingest_kb.py        Embeds KB into Chroma
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                   React + Vite + nginx
│   ├── src/
│   │   ├── App.jsx             Persona-switching chat UI
│   │   ├── api.js              Backend client
│   │   └── styles.css          Editorial design system
│   ├── nginx.conf
│   └── Dockerfile
├── docs/
│   ├── DEPLOYMENT.md           Cloud deployment guide
│   ├── GUARDRAILS.md           Safety architecture
│   └── ERP_INTEGRATION.md      Connecting your ERP
├── docker-compose.yml
└── README.md
```

---

## License & credits

Open source, MIT-licensed reference implementation. Built with FastAPI, LangChain, Chroma, Ollama, and React — full credits in `requirements.txt` and `package.json`.

If you deploy this for a real school, we'd love to hear about it.
