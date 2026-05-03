"""/chat endpoint — main conversation surface."""
from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from app.core.agent import run_agent
from app.core.guardrails import check_input, check_output
from app.models.schemas import ChatRequest, ChatResponse, Source

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    if not req.messages:
        raise HTTPException(400, "At least one message is required.")
    last_user = next((m for m in reversed(req.messages) if m.role == "user"), None)
    if not last_user:
        raise HTTPException(400, "No user message found.")

    # Input guardrail
    g = check_input(last_user.content, req.persona)
    if not g.ok:
        return ChatResponse(
            content=f"⚠️ {g.reason}",
            agent="Guardrails",
            sources=[Source(type="system", title="Blocked")],
            blocked=True,
            block_reason=g.reason,
        )

    # Replace last user message with cleaned (PII-redacted) version for downstream
    safe_messages = list(req.messages)
    safe_messages[-1] = type(safe_messages[-1])(role="user", content=g.cleaned or last_user.content)

    try:
        resp = await run_agent(
            persona=req.persona,
            messages=safe_messages,
            user_id=req.user_id,
            use_rag=req.use_rag,
            use_erp=req.use_erp,
        )
    except Exception as e:
        logger.exception("Agent failed")
        raise HTTPException(500, f"Agent error: {e}")

    # Output guardrail
    sanitized, modified = check_output(resp.content)
    resp.content = sanitized
    if modified:
        resp.sources.append(Source(type="system", title="Output sanitized"))
    return resp
