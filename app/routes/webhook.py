from fastapi import APIRouter, Form, Response
import os
import html

# Try to initialize OpenAI client (optional)
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    client = None

router = APIRouter()

def ai_reply(body_text: str, media_url: str | None) -> str:
    """
    Generates a short farming-related AI reply or a fallback message.
    """
    if not client:
        return "👋 Hi! I got your message. (AI disabled — please set OPENAI_API_KEY)."

    prompt = (
        "You are AgriAgent, a concise, practical assistant for smallholder farmers. "
        "Give helpful, safe, farming-specific advice in one short paragraph."
    )

    user_input = f"Farmer says: {body_text or '(no text)'}"
    if media_url:
        user_input += f"\nThey also sent an image: {media_url}"

    try:
        completion = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input},
            ],
            max_output_tokens=180,
        )
        return completion.output_text.strip() or "✅ Message received!"
    except Exception as e:
        return f"AI error: {e}"

@router.post("/webhook")
async def whatsapp_webhook(
    From: str = Form(default=""),
    Body: str = Form(default=""),
    MediaUrl0: str | None = Form(default=None),
    MediaContentType0: str | None = Form(default=None),
):
    """
    Receives WhatsApp messages via Twilio webhook and returns a TwiML reply.
    """
    print(f"📩 Message from {From}: {Body}")
    if MediaUrl0:
        print(f"📷 Media received: {MediaUrl0} ({MediaContentType0})")

    reply = ai_reply(Body, MediaUrl0)
    safe_reply = html.escape(reply, quote=True)
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe_reply}</Message></Response>'

    return Response(content=twiml, media_type="application/xml")
