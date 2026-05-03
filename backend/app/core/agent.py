"""
Agent Router.

Decides — for each user turn — whether to:
- answer from the RAG knowledge base (policies, FAQs, calendar, fee structure …)
- query the ERP (live personalized data: my attendance, my fees, my marks …)
- answer with general LLM knowledge (greetings, simple chit-chat about school)
- combine RAG + ERP

The router uses a small intent classifier (regex first, LLM fallback) so we
don't burn an LLM call on every simple "hi".
"""
import re
import time
from typing import List

from loguru import logger

from app.core.llm import llm_complete, get_chat_llm
from app.core.rag import rag_answer
from app.core.erp_connector import answer_with_erp, is_erp_connected
from app.models.schemas import ChatMessage, ChatResponse, Source


# ── Persona system prompts (mirror the frontend) ──────────────────────────
PERSONA_SYSTEM = {
    "student": (
        "You are EduBot, a friendly AI assistant for STUDENTS. Help with academics, homework, "
        "timetable queries, attendance, exam schedules, assignments, and school activities. "
        "Be encouraging, patient, and clear. Always tell the truth; if you don't have data, "
        "say so and suggest who to ask."
    ),
    "teacher": (
        "You are EduBot, an AI assistant for TEACHERS. Help with class management, student "
        "performance analytics, attendance reports, curriculum planning, parent communication, "
        "and admin tasks. Be professional and data-driven."
    ),
    "parent": (
        "You are EduBot, a caring AI assistant for PARENTS. Help track your child's attendance, "
        "fee payments, exam results, homework status, and school events. Be warm, reassuring, "
        "and informative. Never share data about other children."
    ),
    "admin": (
        "You are EduBot, an AI assistant for school ADMINISTRATORS. Help with admissions, fee "
        "management, staff scheduling, bulk reports, compliance, and school-wide analytics. "
        "Be precise and concise."
    ),
}


# ── Intent rules ───────────────────────────────────────────────────────────
ERP_PATTERNS = [
    r"\bmy\s+(attendance|fees?|dues?|marks?|grades?|results?|homework|assignment)",
    r"\b(check|show|fetch|get|view|list|generate|report)\b.+\b(attendance|fees?|marks?|results?|students?|teachers?|staff|admissions?)\b",
    r"\bhow many\b", r"\bcount of\b", r"\btotal\b.+\b(students?|fees?|attendance)\b",
    r"\b(today'?s|this week'?s|this month'?s)\b.+\b(class|attendance|schedule|timetable)\b",
    r"\bwho (is|are)\b.+\b(absent|present|enrolled)\b",
    r"\bpending\b.+\b(fees?|payments?|admissions?)\b",
]

KB_PATTERNS = [
    r"\b(policy|policies|rule|guideline|procedure|protocol)\b",
    r"\b(fee structure|exam guidelines|library rules|transport routes|academic calendar)\b",
    r"\b(how (do|to)|what is|when (does|is)|where (is|do))\b",
    r"\b(uniform|holiday|vacation|term|semester|admission process)\b",
]

CHITCHAT = re.compile(r"^\s*(hi|hello|hey|hola|namaste|good\s+(morning|afternoon|evening)|thanks?|thank you|bye)\b", re.I)


def detect_route(text: str) -> str:
    """Return one of: 'erp', 'rag', 'hybrid', 'chat'."""
    if CHITCHAT.match(text):
        return "chat"
    has_erp = any(re.search(p, text, re.I) for p in ERP_PATTERNS)
    has_kb = any(re.search(p, text, re.I) for p in KB_PATTERNS)
    if has_erp and has_kb:
        return "hybrid"
    if has_erp:
        return "erp"
    if has_kb:
        return "rag"
    # Default: RAG — knowledge base is the safest fallback for school questions
    return "rag"


# ── Agent name surface for the UI ─────────────────────────────────────────
def detect_agent_name(text: str) -> str:
    low = text.lower()
    if any(w in low for w in ("attend", "absent", "present")):
        return "Attendance Agent"
    if any(w in low for w in ("fee", "payment", "due")):
        return "Finance Agent"
    if any(w in low for w in ("exam", "result", "grade", "mark")):
        return "Academics Agent"
    if any(w in low for w in ("timetable", "schedule", "class today")):
        return "Schedule Agent"
    if any(w in low for w in ("transport", "bus", "route")):
        return "Transport Agent"
    if any(w in low for w in ("library", "book")):
        return "Library Agent"
    if any(w in low for w in ("admission", "enroll", "tc ", "transfer certificate")):
        return "Admissions Agent"
    if any(w in low for w in ("policy", "rule", "guideline")):
        return "Policy Agent"
    return "EduBot Core"


# ── Main entry point ──────────────────────────────────────────────────────
async def run_agent(
    persona: str,
    messages: List[ChatMessage],
    user_id: str | None,
    use_rag: bool,
    use_erp: bool,
) -> ChatResponse:
    t0 = time.time()
    last_user = next((m for m in reversed(messages) if m.role == "user"), None)
    if not last_user:
        return ChatResponse(content="Please ask a question.", agent="EduBot Core")

    text = last_user.content
    route = detect_route(text)
    agent = detect_agent_name(text)
    logger.info(f"Routing: persona={persona} route={route} agent={agent}")

    sources: List[Source] = []
    answer = ""

    if route == "chat":
        # cheap path — no retrieval
        sys = PERSONA_SYSTEM.get(persona, PERSONA_SYSTEM["student"])
        answer = await llm_complete(sys, text)
        sources = [Source(type="system", title="General")]

    elif route == "erp" and use_erp:
        if not await is_erp_connected():
            answer = ("I couldn't reach the school ERP right now. Please try again in a "
                      "moment or contact the school office.")
            sources = [Source(type="system", title="ERP unavailable")]
        else:
            sql, summary, rows, block = await answer_with_erp(text, persona, user_id)
            if block:
                answer = f"I couldn't run that query: {summary}"
                sources = [Source(type="system", title=f"Blocked: {block}")]
            else:
                answer = summary
                sources = [Source(
                    type="erp",
                    title="School ERP",
                    snippet=f"{len(rows)} row(s) returned",
                )]

    elif route == "rag" and use_rag:
        answer, sources = await rag_answer(text, persona)

    elif route == "hybrid":
        # Run both, then synthesize
        kb_text, kb_src = await rag_answer(text, persona) if use_rag else ("", [])
        erp_block = ""
        erp_src: List[Source] = []
        if use_erp and await is_erp_connected():
            sql, summary, rows, block = await answer_with_erp(text, persona, user_id)
            if not block:
                erp_block = summary
                erp_src = [Source(type="erp", title="School ERP",
                                  snippet=f"{len(rows)} row(s)")]
        sys = PERSONA_SYSTEM.get(persona, PERSONA_SYSTEM["student"])
        synth_user = (
            f"Question: {text}\n\nKnowledge-base finding:\n{kb_text or '(none)'}"
            f"\n\nERP data finding:\n{erp_block or '(none)'}\n\n"
            f"Combine into one helpful answer for the {persona}."
        )
        answer = await llm_complete(sys, synth_user)
        sources = (kb_src or []) + (erp_src or [])

    else:
        sys = PERSONA_SYSTEM.get(persona, PERSONA_SYSTEM["student"])
        answer = await llm_complete(sys, text)
        sources = [Source(type="system", title="General")]

    return ChatResponse(
        content=answer,
        agent=agent,
        sources=sources,
        latency_ms=int((time.time() - t0) * 1000),
    )
