# EduBot — Guardrails & Safety Architecture

EduBot is built for **all four school stakeholders**: students, teachers, parents, administrators. Each group has different access rights and different risk profiles. The guardrail system enforces those boundaries automatically — no admin needs to remember to flip switches.

---

## The seven layers

```
┌──────────────────────────────────────────────────────────────┐
│  1. Rate limiting           ← per-IP, per-minute             │
│  2. Input length / shape    ← oversized / malformed prompts  │
│  3. Profanity filter        ← both directions                │
│  4. PII redaction           ← phones, emails, IDs in logs    │
│  5. Topical scoping         ← school-domain only             │
│  6. Role guardrail          ← cross-record access blocked    │
│  7. Output post-check       ← key leaks, abusive content     │
└──────────────────────────────────────────────────────────────┘
```

Plus the **structural guardrails** baked into the architecture:

- **ERP access is read-only.** Even if the LLM hallucinates `DELETE FROM students`, the SQL safety check rejects it before it reaches the database.
- **RAG-grounded answers.** Policy questions are answered from indexed KB articles. The LLM is instructed not to invent policy.
- **Sources are always cited.** The UI displays `kba` / `erp` / `web` tags so users see exactly where an answer came from.

---

## Layer 1 — Rate limiting

Implementation: [`slowapi`](https://github.com/laurentS/slowapi) middleware in `app/main.py`.
Default: **30 requests/IP/minute**. Configurable via `RATE_LIMIT_PER_MINUTE` in `.env`.

Why: prevents a single bad actor from running up your LLM bill or DOS-ing the school.

---

## Layer 2 — Input shape

Implementation: `guardrails.check_input()`.

- Hard cap at 4 KB per message (configurable: `MAX_INPUT_CHARS`)
- Empty / whitespace-only rejected
- Repeated identical characters past 50 chars rejected ("aaaaaa..." attacks)

---

## Layer 3 — Profanity

Implementation: [`better-profanity`](https://github.com/snguyenthanh/better_profanity) with a fallback word-list if the library isn't available.

- **Inbound**: profanity in user message → polite refusal, no LLM call.
- **Outbound**: profanity in LLM response → censored before being sent to user.

This is intentionally simple. Tune the word list for your school's language.

---

## Layer 4 — PII redaction

Implementation: `guardrails.redact_pii()`.

Patterns detected and replaced **in logs only** (the user still sees their own data):

| Type      | Pattern                                  | Example                                                  |
| --------- | ---------------------------------------- | -------------------------------------------------------- |
| Email     | RFC-ish email regex                      | `aarav.s@school.in` → `[EMAIL_REDACTED]`                 |
| Phone     | India 10-digit mobile, optional `+91`    | `+91-9876543210` → `[PHONE_REDACTED]`                    |
| Aadhaar   | 12 digits                                | `1234 5678 9012` → `[AADHAAR_REDACTED]`                  |
| PAN       | 5 letters + 4 digits + 1 letter          | `ABCDE1234F` → `[PAN_REDACTED]`                          |
| Card      | 13–19 digits with optional separators    | `4111-1111-1111-1111` → `[CARD_REDACTED]`                |

**This is for log hygiene, not for the user-facing answer.** A parent asking *"what's my phone number on file"* still gets a sensible answer — only the server's structured logs and audit trail are scrubbed.

If you operate in a region with different identifiers (US SSN, UK NIN, EU passport formats), add patterns to `PII_PATTERNS` in `guardrails.py`.

---

## Layer 5 — Topical scoping

Implementation: `guardrails.looks_school_related()`.

EduBot refuses to answer questions outside the school domain. This isn't about being unhelpful — it's about scope discipline. A school assistant that suddenly writes crypto trading bots is one news headline away from being banned.

Heuristic: presence of school-related keywords (subjects, role names, policy terms, calendar terms, ERP table names) **or** a clear question structure with school-domain entities. When in doubt, the heuristic errs **on letting it through** but tags the response with a "general knowledge" caveat.

Override: `ENABLE_OFF_TOPIC_FILTER=false` in `.env` if you'd rather allow free-form queries.

---

## Layer 6 — Role guardrail

The most important layer. Implementation: `guardrails.role_violation()`.

| Persona       | Can ask about                                  | Cannot ask about                                   |
| ------------- | ---------------------------------------------- | -------------------------------------------------- |
| Student       | Themselves, public school info                 | Other students, teachers, fees, exam answer keys   |
| Parent        | Their own children's records                   | Other students, teachers' personal data, salaries  |
| Teacher       | Their classes, public school info              | HR data on other staff, fees outside their classes |
| Administrator | Anything on the read-only ERP                  | Modifying anything (system is RO)                  |

The guardrail uses a combination of:

1. **Pattern matching** — if a student says *"show me Aarav's attendance"* and they aren't Aarav, refuse.
2. **Identity scoping** — every request includes a `user_id`. NL→SQL automatically scopes queries to that user's records.
3. **System prompt reinforcement** — the persona system prompt explicitly forbids cross-user lookups.

This is defense in depth. Layer 1 catches obvious attempts; layer 2 catches sneaky ones; layer 3 catches LLM mistakes.

---

## Layer 7 — Output post-check

Implementation: `guardrails.check_output()`.

After the LLM responds, before we return it to the user:

- Strip anything that looks like an API key (`sk-`, `xoxb-`, `AKIA`, etc.)
- Censor profanity that slipped through
- Cap response length (default 8 KB)
- Reject responses that contain SQL DML (in case the LLM tried to be "helpful")

---

## SQL safety (separate from guardrails)

Even though `ERP_READ_ONLY=true` is the default, the connector enforces it at multiple levels:

```python
# app/core/erp_connector.py — is_safe_sql()
1. Reject if SQL contains ';' (no statement chaining)
2. Reject DDL keywords: CREATE/ALTER/DROP/TRUNCATE/RENAME
3. Reject DML keywords: INSERT/UPDATE/DELETE/MERGE/REPLACE
4. Require a SELECT or WITH ... SELECT prefix
5. Limit results (default LIMIT 100) when not specified
```

In production, **also configure your database user to be read-only**. The application enforces it; the database should too.

---

## Auditability

Every NL→SQL query is logged with:

- `user_id`, `persona`, `session_id`
- The original question
- The generated SQL
- Whether it was blocked, and why
- Row count returned

The UI shows the generated SQL alongside every ERP-driven answer. Nothing is hidden from the user. Administrators can review the audit trail in the structured logs.

---

## What guardrails *don't* do

Honest list of what's NOT in scope:

- **They don't make EduBot HIPAA/FERPA-compliant by themselves.** Compliance is a process, not a feature.
- **They don't prevent prompt injection 100%.** Strong system prompts + read-only ERP + role scoping make it hard, but novel attacks are an ongoing arms race.
- **They don't catch every off-topic query.** A student asking about *"the chemistry of explosives for our science fair"* might pass the heuristic. Use your judgment when configuring `ENABLE_OFF_TOPIC_FILTER`.
- **They don't replace human review.** For consequential decisions (disciplinary actions, fee disputes), keep a human in the loop.

---

## Tuning for your school

In `backend/.env`:

```bash
ENABLE_PII_REDACTION=true       # log scrubbing
ENABLE_PROFANITY_FILTER=true    # in/out
ENABLE_OFF_TOPIC_FILTER=true    # school-domain scoping
RATE_LIMIT_PER_MINUTE=30        # per-IP
MAX_INPUT_CHARS=4000            # message cap
ERP_READ_ONLY=true              # ← never disable this in production
```

Need stricter defaults (e.g. for primary schools)? Subclass `guardrails.py` and tighten:
- Topic filter to subject-only
- Length cap to 1 KB
- Profanity threshold including mild words
- Role scoping rejecting any third-person reference at all

The intent is for the safety layer to be **legible and editable**, not a black box you buy from a vendor.
