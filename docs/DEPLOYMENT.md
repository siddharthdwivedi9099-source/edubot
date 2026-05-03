# EduBot — Deployment Guide

Three deployment shapes covered here, from cheapest to most enterprise:

1. [**Single-VPS / Docker Compose**](#1-single-vps--docker-compose) — for one school, ~$10/mo
2. [**Managed PaaS**](#2-managed-paas-railway-render-flyio) — Railway / Render / Fly.io, near-zero ops
3. [**Cloud-native (AWS / GCP / Azure)**](#3-cloud-native) — multi-school, regional resilience

Plus: [**Production checklist**](#production-checklist) and [**ERP migration**](#erp-migration-path).

---

## 1. Single VPS / Docker Compose

The simplest "real" deployment: one virtual machine, everything in containers, HTTPS via a Caddy or Traefik front.

### Server requirements
| Path                       | RAM       | CPU     | Disk    | Notes                                    |
| -------------------------- | --------- | ------- | ------- | ---------------------------------------- |
| Ollama (local LLM)         | **16 GB** | 4 vCPU  | 30 GB   | llama3.1:8b weights ~5 GB                |
| OpenAI / Anthropic         | 2 GB      | 1 vCPU  | 5 GB    | Backend is light without local LLM       |

### Steps

```bash
# 1. SSH in, install Docker
curl -fsSL https://get.docker.com | sh

# 2. Clone + configure
git clone <your-repo> /opt/edubot && cd /opt/edubot
cp backend/.env.example backend/.env
nano backend/.env       # set LLM_PROVIDER, ERP_DB_URL, etc.

# 3. Bring it up
docker compose up -d --build
docker compose exec backend python scripts/ingest_kb.py
```

### Add HTTPS (Caddy, 5 minutes)

Create `/opt/edubot/Caddyfile`:

```
edubot.your-school.in {
    reverse_proxy localhost:8080
}
```

Then:

```bash
docker run -d --name caddy --restart unless-stopped \
  --network host \
  -v /opt/edubot/Caddyfile:/etc/caddy/Caddyfile \
  -v caddy_data:/data \
  caddy:2
```

Caddy obtains a free Let's Encrypt cert automatically. Done.

---

## 2. Managed PaaS (Railway, Render, Fly.io)

The fastest path if you don't want to run a VM. Use a hosted LLM (OpenAI/Anthropic) since most PaaS containers don't have enough RAM for Ollama.

### Backend on Railway

1. Push the repo to GitHub.
2. In Railway, **New → Deploy from GitHub** → pick the repo.
3. Set the **service root** to `backend/` and **Dockerfile path** to `backend/Dockerfile`.
4. Add environment variables (from `backend/.env.example`), at minimum:
   ```
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-...
   ERP_DB_URL=postgresql+asyncpg://...   # see ERP migration below
   APP_CORS_ORIGINS=https://edubot.vercel.app
   ```
5. Add a Railway **Volume** mounted at `/app/app/data` so the Chroma vector store and any local SQLite survive restarts.
6. After first deploy, run a one-shot:
   ```bash
   railway run python scripts/ingest_kb.py
   ```

Same idea on **Render** (web-service from Dockerfile) or **Fly.io** (`fly launch` in `backend/`, then `fly deploy`).

### Frontend on Vercel / Netlify

```bash
cd frontend
# Vercel
npx vercel --prod
# Netlify
npx netlify deploy --prod
```

Set the build env var `VITE_API_BASE_URL=https://your-backend.up.railway.app` so the static build hits the right backend.

---

## 3. Cloud-native

For districts or chains running EduBot across many schools, here's the architecture we recommend.

### AWS reference

```
                                   ┌──────────────────┐
                                   │  Route 53 + ACM  │
                                   └────────┬─────────┘
                                            ▼
                            ┌────────────────────────────────┐
                            │   CloudFront → S3 (frontend)   │
                            └────────────────────────────────┘
                                            │
                                            ▼  /api/*
                            ┌────────────────────────────────┐
                            │   ALB → ECS Fargate (backend)  │
                            └────────┬───────────────┬───────┘
                                     │               │
                          ┌──────────▼─────┐   ┌─────▼────────────┐
                          │  RDS Postgres  │   │  EFS (Chroma DB) │
                          │  (read replica │   │  shared volume   │
                          │   of school    │   └──────────────────┘
                          │   ERP)         │
                          └────────────────┘
                                     │
                          ┌──────────▼─────┐
                          │  Secrets Mgr   │  API keys, DB creds
                          └────────────────┘
```

Key choices:

- **Frontend** → S3 + CloudFront. Static files, basically free.
- **Backend** → ECS Fargate behind an ALB. Auto-scale 1–N tasks based on CPU.
- **LLM** → call OpenAI/Anthropic over the internet; `bedrock-runtime` if you want VPC-private. Don't run Ollama on Fargate — RAM is too pricey.
- **Vector DB** → Chroma persistence on EFS, *or* swap to managed pgvector on RDS.
- **ERP** → connect to a **read replica** of the school ERP database, never the primary. EduBot is read-only but defence in depth is non-negotiable.
- **Secrets** → AWS Secrets Manager; inject as env vars at task start.

GCP equivalent: Cloud Run + Cloud SQL + GCS + Secret Manager. Azure: Container Apps + Azure SQL + Blob Storage + Key Vault.

---

## Production checklist

Before going live with a real school, walk this list.

### Security
- [ ] **HTTPS only** — never serve EduBot over plain HTTP. Caddy/Cloudflare/ACM all give free certs.
- [ ] **Read-only ERP user** — verify `ERP_READ_ONLY=true` AND the DB user has no `INSERT/UPDATE/DELETE` grants.
- [ ] **Rotate API keys** — OpenAI/Anthropic/Twilio keys live in a secrets manager, not git.
- [ ] **CORS** — `APP_CORS_ORIGINS` lists ONLY your real domains.
- [ ] **Rate limit** — `RATE_LIMIT_PER_MINUTE` set appropriately (default 30/IP/min).
- [ ] **Logging** — don't log the request body in plaintext; PII redaction is on by default — keep it on.

### Reliability
- [ ] **Backups** — back up the Chroma volume and the demo SQLite if you keep it.
- [ ] **Health probes** — your platform pings `GET /health` for readiness.
- [ ] **Resource limits** — set memory limits; LLM responses can spike.
- [ ] **Timeouts** — frontend & nginx already at 120s; tune up for slower LLM endpoints.

### Privacy & compliance
- [ ] **Data residency** — if your school is bound by India's DPDP / GDPR / FERPA, host the LLM and DB in-region.
- [ ] **Audit log** — every NL→SQL query is already logged; ensure you retain it for the legally required period.
- [ ] **Parental consent** — for students under 18, get explicit parental consent for AI use.
- [ ] **Right-to-be-forgotten** — when a student leaves, purge their messages from chat history.

---

## ERP migration path

If you're moving from the demo SQLite to a real school ERP, here's the sequence.

### Step 1 — Identify the database

Talk to your ERP vendor; most school ERPs (Fedena, Schoolyard, Edmingle, Skoolbeep, custom builds) are MySQL or PostgreSQL under the hood. Get:

- DB host / port / name
- Read-only credentials (request these specifically — the vendor will know how)
- Schema documentation, or at least a list of important tables

### Step 2 — Map the tables

EduBot is schema-agnostic, but it works best when key tables follow recognisable names. If your ERP uses `tbl_pupil` instead of `students`, create a database **view** to expose a friendlier name:

```sql
CREATE VIEW students AS
  SELECT pupil_id   AS id,
         full_name  AS name,
         class_code AS class,
         section_id AS section
    FROM tbl_pupil;
```

This is the lowest-risk integration: zero changes to the ERP itself.

### Step 3 — Point EduBot at it

```bash
# in backend/.env
ERP_DB_URL=mysql+asyncmy://edubot_ro:strong-pass@erp.school.local:3306/school_erp
ERP_READ_ONLY=true
ERP_ALLOWED_TABLES=students,teachers,attendance,fees,exam_results,timetable,classes
```

`ERP_ALLOWED_TABLES` is an optional allowlist — if set, the NL→SQL pipeline can only see these tables. Useful for hiding HR/payroll data when only academic data should be exposed.

### Step 4 — Smoke test

```bash
curl http://localhost:8000/erp/health
curl http://localhost:8000/erp/schema
curl -X POST http://localhost:8000/erp/query \
     -H 'Content-Type: application/json' \
     -d '{"question":"How many students are in grade 8?","persona":"admin"}'
```

You should see the generated SQL, the row count, and a friendly summary.

### Step 5 — Tighten access

Even with `ERP_READ_ONLY=true`, request your DBA enforce it at the database level too:

```sql
-- MySQL
GRANT SELECT ON school_erp.* TO 'edubot_ro'@'%';

-- Postgres
GRANT CONNECT ON DATABASE school_erp TO edubot_ro;
GRANT USAGE ON SCHEMA public TO edubot_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO edubot_ro;
```

---

## Scaling notes

- A single 4-vCPU / 8 GB backend handles roughly **50–100 concurrent chats** when using a hosted LLM (OpenAI/Anthropic). Latency is dominated by the LLM itself.
- The **vector store** (Chroma) scales to ~1M chunks on commodity hardware. For more, swap to **pgvector** or **Qdrant**.
- The **bottleneck is rarely EduBot** — it's the school ERP. Use a read replica.
- For **multi-tenant** (a chain of schools), run one backend per school and share a Chroma collection per school. Don't try to multiplex tenants in a single index — privacy complications outweigh the savings.

---

## FAQ

**Q: Can I run this fully offline?**
A: Yes. Use Ollama for the LLM, Chroma is embedded, SQLite for the ERP demo, no internet calls. WhatsApp is the only feature that requires external connectivity.

**Q: How much does it cost to run for one school of 1,000 students?**
A: With OpenAI gpt-4o-mini and a $20/mo VPS: roughly **$30–80/mo** for moderate use. Fully self-hosted on a 16 GB VPS: **$30/mo flat**.

**Q: Will it work in Hindi / regional languages?**
A: The LLM handles multilingual queries natively. The KB is currently English-first; translate the JSON or run it through a translation pipeline once. The Web Speech API supports `hi-IN`, `en-IN`, `ta-IN`, etc. — change `lang` in `App.jsx`.

**Q: Can teachers upload their own documents?**
A: There's a `POST /kb/ingest` endpoint that accepts new articles. We deliberately didn't build a UI uploader yet — schools have wildly different document-approval workflows. Wire it to your CMS or build a simple admin page.
