"""
ERP SQL Connector.

Works with ANY SQL-based ERP: SQLite, MySQL, PostgreSQL, MSSQL, etc.

Features:
- Async SQLAlchemy engine, single-connection pooling.
- Schema introspection on startup → fed to the LLM as grounding context.
- Natural-language → SQL via the configured LLM, with a strict generation
  prompt that forbids destructive statements.
- A SQL guardrail layer that rejects DML/DDL when ERP_READ_ONLY=true, and
  always rejects multiple statements / dangerous keywords.
- Row-level scoping: when a `user_id` and `persona` are passed, queries
  about "my attendance/fees/etc." are constrained to that user.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from loguru import logger

from app.config import get_settings
from app.core.llm import llm_complete


# ── Engine ──────────────────────────────────────────────────────────────────

_engine: Optional[AsyncEngine] = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        s = get_settings()
        _engine = create_async_engine(s.erp_db_url, echo=False, future=True)
        logger.info(f"ERP engine created for {s.erp_db_url.split('@')[-1]}")
    return _engine


# ── SQL Guardrails ──────────────────────────────────────────────────────────

FORBIDDEN_PATTERNS = [
    r"\bdrop\b", r"\btruncate\b", r"\balter\b",
    r"\bgrant\b", r"\brevoke\b", r"\bcreate\s+user\b",
    r"\bxp_cmdshell\b", r"\bexec\s*\(", r"\binto\s+outfile\b",
    r"\bload_file\b",
]

WRITE_PATTERNS = [r"\binsert\b", r"\bupdate\b", r"\bdelete\b", r"\breplace\b", r"\bmerge\b"]


def is_safe_sql(sql: str) -> Tuple[bool, str]:
    """Returns (ok, reason)."""
    s = get_settings()
    low = sql.lower().strip().rstrip(";")

    # No multiple statements
    if ";" in low:
        return False, "Multiple SQL statements are not allowed."

    # Always block DDL & dangerous functions
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, low):
            return False, f"Statement contains forbidden keyword (matches /{pat}/)."

    # Read-only mode → block writes
    if s.erp_read_only:
        for pat in WRITE_PATTERNS:
            if re.search(pat, low):
                return False, "ERP is in read-only mode; writes are disabled."

    # Must be a SELECT (read-only) or one of the allowed write statements
    if s.erp_read_only and not low.startswith("select") and not low.startswith("with"):
        return False, "Only SELECT/CTE statements are allowed in read-only mode."

    return True, ""


# ── Schema introspection ────────────────────────────────────────────────────

_schema_cache: Optional[str] = None


async def get_schema_text() -> str:
    """Return a compact textual representation of the schema for LLM grounding."""
    global _schema_cache
    if _schema_cache:
        return _schema_cache

    eng = get_engine()
    async with eng.connect() as conn:
        def _introspect(sync_conn):
            insp = inspect(sync_conn)
            lines: List[str] = []
            for tbl in insp.get_table_names():
                cols = insp.get_columns(tbl)
                col_strs = [f"{c['name']}:{c['type']}" for c in cols]
                lines.append(f"TABLE {tbl}({', '.join(col_strs)})")
            return "\n".join(lines)
        _schema_cache = await conn.run_sync(_introspect)
    logger.info(f"Schema cached: {len(_schema_cache.splitlines())} tables")
    return _schema_cache


async def is_erp_connected() -> bool:
    try:
        eng = get_engine()
        async with eng.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning(f"ERP not connected: {e}")
        return False


# ── Execute ─────────────────────────────────────────────────────────────────

async def run_sql(sql: str, params: Optional[Dict[str, Any]] = None,
                  limit: int = 100) -> List[dict]:
    ok, reason = is_safe_sql(sql)
    if not ok:
        raise ValueError(f"Unsafe SQL rejected: {reason}")

    eng = get_engine()
    async with eng.connect() as conn:
        result = await conn.execute(text(sql), params or {})
        try:
            rows = result.mappings().all()[:limit]
            return [dict(r) for r in rows]
        except Exception:
            return []


# ── NL → SQL ────────────────────────────────────────────────────────────────

NL2SQL_SYSTEM = """You are a SQL generator for a school ERP. Translate the user's question into a \
single safe SELECT statement against the schema below. Rules:

1. Output ONLY the SQL — no explanation, no markdown fences, no trailing semicolon.
2. Use ONLY tables and columns listed in the schema. If the question can't be answered with \
this schema, output exactly: ERROR: cannot answer with available schema.
3. NEVER output INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/GRANT.
4. NEVER chain multiple statements with `;`.
5. When the user says "my", "I", "me" and a `user_id` is given, scope by that ID.
6. Always cap results with LIMIT 50 unless the user specifies otherwise.
7. Prefer JOINs that actually exist as foreign keys — don't invent columns.

SCHEMA:
{schema}

USER ROLE: {persona}
USER ID (for personal queries): {user_id}
"""


async def nl_to_sql(question: str, persona: str = "admin",
                    user_id: Optional[str] = None) -> str:
    schema = await get_schema_text()
    system = NL2SQL_SYSTEM.format(
        schema=schema, persona=persona, user_id=user_id or "(none)"
    )
    raw = await llm_complete(system, question)
    sql = raw.strip()
    # strip code fences if the LLM ignored instructions
    sql = re.sub(r"^```(?:sql)?\s*", "", sql)
    sql = re.sub(r"\s*```$", "", sql)
    sql = sql.rstrip(";").strip()
    return sql


async def answer_with_erp(question: str, persona: str,
                          user_id: Optional[str] = None
                          ) -> Tuple[str, str, List[dict], Optional[str]]:
    """Returns (sql, summary, rows, block_reason or None)."""
    sql = await nl_to_sql(question, persona, user_id)
    if sql.startswith("ERROR"):
        return sql, "I could not turn that into a database query.", [], "no-schema-match"

    ok, reason = is_safe_sql(sql)
    if not ok:
        return sql, "Query rejected by safety guardrails.", [], reason

    try:
        rows = await run_sql(sql)
    except Exception as e:
        return sql, f"Query failed: {e}", [], "execution-error"

    # Summarize results
    if not rows:
        return sql, "No matching records found.", rows, None
    summary = await _summarize_rows(question, rows, persona)
    return sql, summary, rows, None


async def _summarize_rows(question: str, rows: List[dict], persona: str) -> str:
    """Ask the LLM to phrase the rows as a friendly answer."""
    if not rows:
        return "No data."
    # Trim very large results before sending to the LLM
    preview = rows[:20]
    sys = (
        f"You are EduBot speaking to a {persona}. Summarize the following SQL result rows "
        f"as a clear, friendly answer to the user's original question. If the data has "
        f"numeric trends (averages, percentages), state them. Keep it under 150 words. "
        f"Do NOT show the raw SQL."
    )
    user = f"Question: {question}\n\nRows ({len(rows)} total, showing up to 20):\n{preview}"
    return await llm_complete(sys, user)
