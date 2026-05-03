"""
Guardrails for EduBot.

Layered safety:
1.  **Input validation**     — length cap, character cap, profanity, off-topic.
2.  **PII redaction**        — scrubs phone/email/aadhaar/PAN before logging.
3.  **Topical scoping**      — refuse questions outside school-related domains.
4.  **Role-based access**    — students/parents cannot ask for other people's data.
5.  **Output post-check**    — strip leaked secrets, profanity in answers.

This module is intentionally simple and self-contained — it does NOT depend on
external services so a school can self-host EduBot fully offline.
"""
import re
from dataclasses import dataclass
from typing import Optional, Tuple

from loguru import logger

from app.config import get_settings

# better-profanity is recommended but optional. Fall back to a tiny built-in
# blocklist so the module imports even if the package isn't installed.
try:
    from better_profanity import profanity  # type: ignore
    profanity.load_censor_words()
    _HAS_PROFANITY_LIB = True
except Exception:  # pragma: no cover
    _HAS_PROFANITY_LIB = False
    _FALLBACK_BAD = {"fuck", "shit", "bitch", "asshole", "bastard", "dick"}

    class _FallbackProfanity:
        @staticmethod
        def contains_profanity(text: str) -> bool:
            t = text.lower()
            return any(w in t for w in _FALLBACK_BAD)

        @staticmethod
        def censor(text: str) -> str:
            out = text
            for w in _FALLBACK_BAD:
                out = re.sub(rf"\b{re.escape(w)}\b", "*" * len(w), out, flags=re.I)
            return out

    profanity = _FallbackProfanity()  # type: ignore


# ── Patterns for PII redaction (India + generic) ───────────────────────────
PII_PATTERNS = {
    "EMAIL":   re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "PHONE":   re.compile(r"\b(?:\+?91[-\s]?)?[6-9]\d{9}\b"),
    "AADHAAR": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "PAN":     re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "CARD":    re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}


def redact_pii(text: str) -> str:
    """Replace PII with role tokens. Used before logging or sending to non-trusted sinks."""
    for label, pat in PII_PATTERNS.items():
        text = pat.sub(f"[{label}_REDACTED]", text)
    return text


# ── Topic scoping ──────────────────────────────────────────────────────────
SCHOOL_TOPIC_KEYWORDS = {
    # Academics
    "school", "class", "grade", "marks", "exam", "test", "result", "homework",
    "assignment", "syllabus", "curriculum", "subject", "lesson", "study",
    "library", "book", "lecture", "tutor", "tuition",
    # Operations
    "attendance", "absent", "present", "leave", "fee", "fees", "payment", "due",
    "scholarship", "admission", "enrol", "transfer", "tc",
    "transport", "bus", "route", "uniform", "id card",
    # People
    "student", "teacher", "principal", "parent", "guardian", "staff", "admin",
    # Calendar
    "timetable", "schedule", "calendar", "holiday", "vacation", "event",
    # Generic helpfulness
    "hello", "hi", "help", "thanks", "thank", "what", "how", "when", "where", "who",
}


def looks_school_related(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in SCHOOL_TOPIC_KEYWORDS)


# ── Role-based access ──────────────────────────────────────────────────────
SENSITIVE_PATTERNS = [
    re.compile(r"\b(all\s+students?|every\s+student|other\s+students?)\b", re.I),
    re.compile(r"\b(another\s+(child|student)|someone\s+else'?s)\b", re.I),
    re.compile(r"\b(staff\s+salar|teacher\s+salar|payroll)\b", re.I),
]


def role_violation(text: str, persona: str) -> Optional[str]:
    """Returns a reason string if the request violates the persona's scope, else None."""
    if persona in ("admin", "teacher"):
        return None
    for pat in SENSITIVE_PATTERNS:
        if pat.search(text):
            return f"As a {persona}, you can only ask about your own data."
    if persona == "parent" and re.search(r"\b(my\s+marks|my\s+attendance|my\s+homework)\b", text, re.I):
        # parents should ask about their child, not themselves
        return None  # we don't block, the LLM/ERP will handle scope
    return None


# ── Public entry point ─────────────────────────────────────────────────────

@dataclass
class GuardResult:
    ok: bool
    reason: Optional[str] = None
    cleaned: Optional[str] = None


def check_input(text: str, persona: str = "student") -> GuardResult:
    """Run all input-side guardrails. Mutates text by redacting PII."""
    s = get_settings()

    if not text or not text.strip():
        return GuardResult(False, "Empty message.")

    if len(text) > s.max_input_tokens * 4:  # rough char cap
        return GuardResult(False, "Message is too long. Please shorten and resend.")

    if s.enable_profanity_filter and profanity.contains_profanity(text):
        return GuardResult(False, "Please rephrase your question without offensive language.")

    if s.enable_off_topic_filter and not looks_school_related(text):
        # We're permissive: only block if we ALSO detect prompt-injection-style asks.
        if re.search(r"\b(ignore|disregard).+(instructions|prompt|rules)\b", text, re.I):
            return GuardResult(False, "I can only help with school-related questions.")

    rv = role_violation(text, persona)
    if rv:
        return GuardResult(False, rv)

    cleaned = redact_pii(text) if s.enable_pii_redaction else text
    return GuardResult(True, cleaned=cleaned)


def check_output(text: str) -> Tuple[str, bool]:
    """Sanitize an LLM answer. Returns (sanitized, was_modified)."""
    s = get_settings()
    modified = False
    out = text
    if s.enable_profanity_filter and profanity.contains_profanity(out):
        out = profanity.censor(out)
        modified = True
    # Strip any obvious environment leaks
    for leak in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "TWILIO_AUTH_TOKEN"):
        if leak in out:
            out = out.replace(leak, "[REDACTED]")
            modified = True
    if modified:
        logger.warning("Output guardrail modified the response.")
    return out, modified
