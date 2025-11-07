from fastapi import APIRouter, Form, Response, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os, html

# ==========================================================
# Optional: Initialize OpenAI client (safe fallback if not set)
# ==========================================================
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    client = None

router = APIRouter()

# ==========================================================
# Helper: Generate AI reply or fallback
# ==========================================================
def ai_reply_text(prompt_text: str) -> str:
    """
    Generates an AI reply using OpenAI's Responses API.
    Falls back gracefully if the key or model is unavailable.
    """
    if not client:
        return "👋 I received your message. (AI disabled — please set OPENAI_API_KEY.)"

    try:
        completion = client.responses.create(   # ✅ correct method name
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": (
                    "You are AgriAgent, a concise and practical assistant for smallholder farmers. "
                    "Provide safe, actionable, and context-specific advice in 2–4 short sentences."
                )},
                {"role": "user", "content": prompt_text},
            ],
            max_output_tokens=220,
        )
        return (completion.output_text or "").strip() or "✅ Message received."
    except Exception as e:
        return f"AI error: {e}"

# ==========================================================
# 1️⃣ Health check — used by the app startup screen
# ==========================================================
@router.get("/check")
def check():
    return {
        "ok": True,
        "status": "ok",
        "service": "AgriAgent API",
        "webhook": "/webhook",
        "version": "1.0.0",
    }

# ==========================================================
# 2️⃣ Text endpoint for app (new)
# ==========================================================
class ChatIn(BaseModel):
    text: str

@router.post("/message")
async def message(payload: ChatIn):
    reply = ai_reply_text(f"Farmer says: {payload.text}")
    return {"reply": reply}

# ==========================================================
# 3️⃣ Alias for Flutter apps still calling /chat (old endpoint)
#    - Accepts both {"text": "..."} and {"message": "..."}
# ==========================================================
@router.post("/chat")
async def chat(payload: dict):
    text = payload.get("text") or payload.get("message") or ""
    reply = ai_reply_text(f"Farmer says: {text}")
    return {"reply": reply}

# ==========================================================
# 4️⃣ Image upload endpoint — app sends image for identification
#    - Accepts either "file" or "image" field name
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
        "Describe general guidance on analyzing crop or soil images safely."
    )
    return {"filename": upload.filename, "reply": reply}

# ==========================================================
# 5️⃣ WhatsApp Webhook for Twilio
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
    Handles WhatsApp messages from Twilio.
    Replies with TwiML so Twilio sends back the response automatically.
    """
    print(f"📩 Message from {From}: {Body}")
    if (NumMedia and NumMedia != "0") or MediaUrl0:
        prompt = (
            f"Farmer says: {Body or '(no text)'}\n"
            f"They also sent an image: {MediaUrl0 or '(unavailable)'}"
        )
    else:
        prompt = f"Farmer says: {Body or '(no text)'}"

    reply = ai_reply_text(prompt)
    return twiml_reply(reply)

# ==========================================================
# 6️⃣ Support trailing slash (Twilio compatibility)
# ==========================================================
@router.post("/webhook/")
async def whatsapp_webhook_trailing(
    From: str = Form(default=""),
    Body: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: str | None = Form(default=None),
    MediaContentType0: str | None = Form(default=None),
):
    return await whatsapp_webhook(From, Body, NumMedia, MediaUrl0, MediaContentType0)
