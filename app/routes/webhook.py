from fastapi import APIRouter, Form, Response, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os, html

# ==========================================================
# Initialize OpenAI client safely
# ==========================================================
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    client = None

router = APIRouter()

# ==========================================================
# Helper: AI text generation
# ==========================================================
def ai_reply_text(prompt_text: str) -> str:
    """
    Generates a concise AI reply for farmer messages.
    Compatible with openai>=1.0 (uses chat.completions.create).
    """
    if not client:
        return "👋 I received your message. (AI disabled — please set OPENAI_API_KEY.)"

    try:
        completion = client.chat.completions.create(  # ✅ correct modern method
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are AgriAgent, a concise and practical assistant for smallholder farmers. "
                    "Provide safe, actionable, and context-specific advice in 2–4 short sentences."
                )},
                {"role": "user", "content": prompt_text},
            ],
            max_tokens=220,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"AI error: {e}"

# ==========================================================
# 1️⃣ Health check
# ==========================================================
@router.get("/check")
def check():
    return {
        "ok": True,
        "status": "ok",
        "service": "AgriAgent API",
        "webhook": "/webhook",
        "version": "1.0.1",
    }

# ==========================================================
# 2️⃣ Message endpoints (for app & backward compatibility)
# ==========================================================
class ChatIn(BaseModel):
    text: str | None = None
    message: str | None = None

@router.post("/message")
async def message(payload: ChatIn):
    text = payload.text or payload.message or ""
    reply = ai_reply_text(f"Farmer says: {text}")
    return {"reply": reply}

@router.post("/chat")
async def chat(payload: dict):
    text = payload.get("text") or payload.get("message") or ""
    reply = ai_reply_text(f"Farmer says: {text}")
    return {"reply": reply}

# ==========================================================
# 3️⃣ Image upload endpoint
# ==========================================================
@router.post("/identify")
async def identify(
    file: UploadFile = File(None),
    image: UploadFile = File(None)
):
    upload = file or image
    if not upload:
        raise HTTPException(status_code=400, detail="Please upload an image file.")
    if not upload.content_type or not upload.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a valid image file.")

    reply = ai_reply_text(
        f"A farmer uploaded an image named '{upload.filename}'. "
        "Describe general guidance on analyzing crop, soil, or plant health safely."
    )
    return {"filename": upload.filename, "reply": reply}

# ==========================================================
# 4️⃣ Twilio WhatsApp webhook
# ==========================================================
def twiml_reply(text: str) -> Response:
    safe = html.escape(text, quote=True)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe}</Message></Response>'
    return Response(content=xml, media_type="application/xml")

@router.post("/webhook")
async def whatsapp_webhook(
    From: str = Form(default=""),
    Body: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: str | None = Form(default=None),
    MediaContentType0: str | None = Form(default=None),
):
    """
    Handles incoming WhatsApp messages from Twilio.
    Replies automatically with TwiML.
    """
    print(f"📩 WhatsApp message from {From}: {Body}")
    if (NumMedia and NumMedia != "0") or MediaUrl0:
        prompt = (
            f"Farmer says: {Body or '(no text)'}\n"
            f"They also sent an image: {MediaUrl0 or '(unavailable)'}"
        )
    else:
        prompt = f"Farmer says: {Body or '(no text)'}"

    reply = ai_reply_text(prompt)
    return twiml_reply(reply)

@router.post("/webhook/")
async def whatsapp_webhook_trailing(
    From: str = Form(default=""),
    Body: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: str | None = Form(default=None),
    MediaContentType0: str | None = Form(default=None),
):
    return await whatsapp_webhook(From, Body, NumMedia, MediaUrl0, MediaContentType0)
