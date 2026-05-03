# EduBot — ERP Integration Guide

EduBot is built to plug into **your existing school ERP** without you needing to modify the ERP itself. This document covers what that looks like in practice for the most common setups.

---

## The model

```
┌──────────────┐    SELECT only     ┌──────────────────┐
│   EduBot     │ ─────────────────► │   School ERP DB  │
│   backend    │ ◄───────────────── │   (read replica) │
└──────────────┘     rows back      └──────────────────┘
       │
       │  natural-language Q + schema
       ▼
   LLM generates safe SQL
       │
       ▼
   SQL safety check
       │
       ▼
   Execute, summarise, cite
```

**Three properties matter:**

1. **Read-only.** EduBot never writes to your ERP. Even if the LLM tried, the SQL safety layer would block it.
2. **Schema-aware.** On startup, EduBot introspects your tables and columns and feeds that schema to the LLM as grounding context. No fine-tuning required for new schools.
3. **Auditable.** Every query and its result is logged and shown in the UI.

---

## Supported databases

Anything SQLAlchemy talks to:

| DB                    | URL prefix                                                         |
| --------------------- | ------------------------------------------------------------------ |
| **SQLite** (demo)     | `sqlite+aiosqlite:///./app/data/demo_school.db`                    |
| **MySQL / MariaDB**   | `mysql+asyncmy://user:pass@host:3306/dbname`                       |
| **PostgreSQL**        | `postgresql+asyncpg://user:pass@host:5432/dbname`                  |
| **MS SQL Server**     | `mssql+aioodbc://user:pass@host/dbname?driver=ODBC+Driver+18+for+SQL+Server` |
| **Oracle**            | `oracle+oracledb_async://user:pass@host:1521/?service_name=XE`     |

Set the URL via `ERP_DB_URL` in `backend/.env`.

---

## Configuration reference

```bash
# Required: connection string
ERP_DB_URL=mysql+asyncmy://edubot_ro:strong-pass@erp.school.local:3306/school_erp

# Required: enforce read-only at the application layer
ERP_READ_ONLY=true

# Optional: restrict which tables the LLM can see (allowlist)
# Comma-separated. If unset, ALL tables in the schema are exposed.
ERP_ALLOWED_TABLES=students,teachers,classes,sections,attendance,fees,exam_results,timetable,subjects,transport_routes,library_loans

# Optional: max rows returned per query
ERP_MAX_ROWS=100

# Optional: timeout for individual queries (seconds)
ERP_QUERY_TIMEOUT=15
```

---

## Worked example: integrating with Fedena

Fedena is one of the most common open-source school ERPs in India. Here's the full integration sequence.

### Step 1 — Get a read-only DB user

In MySQL on your Fedena server:

```sql
CREATE USER 'edubot_ro'@'%' IDENTIFIED BY 'replace-with-strong-password';
GRANT SELECT ON fedena.* TO 'edubot_ro'@'%';
FLUSH PRIVILEGES;
```

### Step 2 — Create friendly views

Fedena's tables are named `students`, `employees`, `attendances`, `fee_collections`, `exam_scores`, etc. — already friendly. But it has columns like `is_deleted` and `is_active` that the LLM doesn't need to think about. Hide them:

```sql
USE fedena;

CREATE VIEW v_students AS
SELECT id, first_name, middle_name, last_name, admission_no, batch_id,
       date_of_birth, gender, status, has_paid_fees
  FROM students
 WHERE is_deleted = 0;

CREATE VIEW v_attendance AS
SELECT a.id, a.student_id, a.month_date, a.forenoon, a.afternoon, a.full_day, a.reason
  FROM attendances a
  JOIN students s ON s.id = a.student_id
 WHERE s.is_deleted = 0;

CREATE VIEW v_fees AS
SELECT id, student_id, batch_id, fee_collection_id, transaction_id,
       fees_paid, balance, paid_date, financial_year_id
  FROM finance_transactions
 WHERE transaction_type = 'fee_collection';
```

### Step 3 — Tell EduBot what to expose

```bash
# backend/.env
ERP_DB_URL=mysql+asyncmy://edubot_ro:***@fedena.school.local:3306/fedena
ERP_READ_ONLY=true
ERP_ALLOWED_TABLES=v_students,v_attendance,v_fees,batches,subjects,employees
```

### Step 4 — Verify

```bash
curl http://localhost:8000/erp/health
# {"ok": true, "url": "mysql+asyncmy://...", "read_only": true, "tables": 6}

curl http://localhost:8000/erp/schema
# returns column list for the 6 allowed tables

curl -X POST http://localhost:8000/erp/query \
     -H 'Content-Type: application/json' \
     -d '{"question":"How many students are absent today?","persona":"admin"}'
```

Expected response:
```json
{
  "sql": "SELECT COUNT(*) FROM v_attendance WHERE month_date = CURDATE() AND full_day = 'a'",
  "rows": [[127]],
  "summary": "127 students were marked absent today.",
  "blocked": false
}
```

---

## Integrating with custom or legacy ERPs

If your ERP has unusual table names (`tbl_pupil_master`, `MST_FEE_DTL`), you have two options:

### Option A — Views (recommended)
Wrap the legacy tables in views with friendly names. Zero changes to the ERP, zero risk.

### Option B — Schema hint
You can extend the NL→SQL prompt with a vocabulary mapping. Edit `app/core/erp_connector.py`:

```python
SCHEMA_GLOSSARY = """
- 'students' lives in tbl_pupil_master (columns: pupil_id, full_name, class_code)
- 'attendance' lives in tbl_att_dtl (columns: pupil_id, att_date, att_status)
- 'fees' lives in mst_fee_dtl (columns: pupil_id, fee_amt, fee_paid_date)
"""
```

This is appended to the LLM's NL→SQL system prompt so the model knows the mapping. Less clean than views but useful when DBA cooperation is slow.

---

## Multi-database setups

If your school's data lives in **multiple databases** (academic in MySQL, finance in PostgreSQL), expose the cross-db join via a single view in either DB using **federated tables** (MySQL FEDERATED engine, Postgres `postgres_fdw`, MS SQL linked servers).

Or — simpler — replicate both into a single read-replica DB just for EduBot. ETL daily.

---

## What about MongoDB / NoSQL ERPs?

EduBot's NL→SQL pipeline only handles SQL today. If your ERP is on Mongo/Firestore/DynamoDB:

- **Quick fix**: Replicate the relevant collections into a Postgres read-replica nightly. EduBot queries the replica.
- **Longer-term**: contribute a `nosql_connector.py` — the abstraction in `core/erp_connector.py` is small and well-isolated.

---

## Security hardening

### Network
- Put EduBot's backend in the **same VPC** as the ERP read replica.
- Don't expose the ERP DB to the public internet.
- Use SSL for the DB connection: `?ssl=true&sslmode=require` (Postgres) or equivalent.

### Database
- The DB user has `SELECT` only — verify with `SHOW GRANTS FOR 'edubot_ro'@'%';`.
- Audit the ERP's audit log periodically — confirm no DDL/DML from the EduBot user.

### Application
- `ERP_READ_ONLY=true` (default) — never disable in production.
- `RATE_LIMIT_PER_MINUTE` set to a sensible value.
- Logs scrubbed for PII (default).

### Process
- When a teacher leaves, rotate the DB user password.
- Quarterly review of which tables are in `ERP_ALLOWED_TABLES`. Remove anything no longer needed (least privilege).

---

## Troubleshooting

| Symptom                                              | Likely cause                                              |
| ---------------------------------------------------- | --------------------------------------------------------- |
| `/erp/health` says `ok: false`                       | Wrong `ERP_DB_URL` or DB unreachable from container       |
| `/erp/schema` returns empty `tables` list            | DB user has no SELECT grants on any table                 |
| LLM says "I don't have access to that data"          | Table not in `ERP_ALLOWED_TABLES`, or row blocked by role |
| SQL is generated but query times out                 | Missing index on filtered column; tune the schema         |
| LLM hallucinates wrong column names                  | Reduce `ERP_ALLOWED_TABLES` to focused subset; use views  |
| All ERP queries blocked with "unsafe SQL"            | Check logs for the offending SQL; usually a `;` in input  |

For deeper debugging, run the backend with `LOG_LEVEL=DEBUG` and watch the structured log — every NL→SQL step is logged.
