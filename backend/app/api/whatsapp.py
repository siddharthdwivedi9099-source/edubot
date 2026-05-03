"""
WhatsApp integration via Twilio.

Setup:
1. Create a Twilio account, activate the WhatsApp sandbox or buy a number.
2. Set webhook URL to:  https://YOUR-DOMAIN/whatsapp/inbound
3. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM in .env.

This endpoint accepts Twilio's form-encoded webhook, runs the message through
the same agent pipeline used by the web UI, and replies via TwiML.
"""
from fastapi import APIRouter, Request, Response
from loguru import logger

from app.config import get_settings
from app.core.agent import run_agent
from app.core.guardrails import check_input, check_output
from app.models.schemas import ChatMessage

router = APIRouter()


@router.post("/inbound")
async def inbound(request: Request) -> Response:
    form = await request.form()
    body = (form.get("Body") or "").strip()
    sender = form.get("From") or "unknown"
    logger.info(f"WhatsApp inbound from {sender}: {body[:60]}")

    if not body:
        return _twiml("Hi! I'm EduBot. Ask me anything about your school.")

    # Identify persona from a simple prefix convention; default = parent
    persona = "parent"
    low = body.lower()
    for tag in ("[student]", "[teacher]", "[parent]", "[admin]"):
        if low.startswith(tag):
            persona = tag.strip("[]")
            body = body[len(tag):].strip()
            break

    g = check_input(body, persona)
    if not g.ok:
        return _twiml(f"⚠️ {g.reason}")

    try:
        resp = await run_agent(
            persona=persona,
            messages=[ChatMessage(role="user", content=g.cleaned or body)],
            user_id=sender,  # phone number serves as user_id placeholder
            use_rag=True,
            use_erp=True,
        )
        out, _ = check_output(resp.content)
    except Exception as e:
        logger.exception("WhatsApp agent failed")
        out = f"Sorry, something went wrong: {e}"

    # WhatsApp message limit ~ 1600 chars; trim safely
    if len(out) > 1500:
        out = out[:1500] + "…"
    return _twiml(out)


@router.post("/send")
async def send_outbound(to: str, body: str) -> dict:
    """Manually send a message — used for parent broadcasts, alerts, etc."""
    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token):
        return {"sent": False, "error": "Twilio credentials not configured."}
    from twilio.rest import Client
    client = Client(s.twilio_account_sid, s.twilio_auth_token)
    msg = client.messages.create(
        from_=s.twilio_whatsapp_from,
        to=to if to.startswith("whatsapp:") else f"whatsapp:{to}",
        body=body,
    )
    return {"sent": True, "sid": msg.sid}


def _twiml(text: str) -> Response:
    """Wrap a plain string in a TwiML <Message> response."""
    safe = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response><Message>{safe}</Message></Response>'
    )
    return Response(content=xml, media_type="application/xml")
