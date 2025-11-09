from fastapi import APIRouter, Form, Response, UploadFile, File, HTTPException
from pydantic import BaseModel
import os, html, mimetypes

try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    client = None

router = APIRouter()

# ---------- AI helper ----------
def ai_reply_text(prompt_text: str) -> str:
    """Send text to OpenAI for a structured agronomic reply."""
    if not client:
        return "👋 I received your message. (AI disabled — please set OPENAI_API_KEY.)"
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AgriAgent, an expert agronomist AI for farmers. "
                        "When given a text or image upload notice, provide a clear, structured, and practical answer."
                    ),
                },
                {"role": "user", "content": prompt_text},
            ],
            max_tokens=500,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"AI error: {e}"

# ---------- Health ----------
@router.get("/check")
def check():
    return {"ok": True, "status": "ok", "service": "AgriAgent API", "version": "2.1.0"}

# ---------- Text ----------
class ChatIn(BaseModel):
    text: str | None = None
    message: str | None = None

@router.post("/chat")
async def chat(payload: dict):
    text = payload.get("text") or payload.get("message") or ""
    reply = ai_reply_text(f"Farmer says: {text}")
    return {"reply": reply}

@router.post("/message")
async def message(payload: ChatIn):
    text = payload.text or payload.message or ""
    reply = ai_reply_text(f"Farmer says: {text}")
    return {"reply": reply}

# ---------- Image ----------
@router.post("/identify")
async def identify(
    file: UploadFile = File(None),
    image: UploadFile = File(None),
    context: str | None = Form(default=None),
):
    """Accepts an uploaded image and context, infers the likely crop/issue."""
    upload = file or image
    if not upload:
        raise HTTPException(status_code=400, detail="No image found. Use 'file' or 'image'.")

    ctype = (upload.content_type or "").lower().strip()
    if not ctype.startswith("image/"):
        guessed, _ = mimetypes.guess_type(upload.filename or "")
        if not guessed or not guessed.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Invalid image type: {ctype or 'unknown'}")

    _ = await upload.read()  # read to consume stream

    prompt = (
        f"A farmer uploaded an image named '{upload.filename}'. "
        f"Extra context: {context or '(none provided)'}.\n\n"
        "You cannot view the image but must infer the most likely crop or animal, problem, cause, and advice.\n"
        "Return your answer **only** in this format:\n\n"
        "Crop/Plant or Animal: <name>\n"
        "Likely Problem: <short diagnosis>\n"
        "Why: <1–2 sentences>\n"
        "Recommended Action: <practical steps>\n"
        "Preventive Tips: <short bullet points>\n"
    )

    try:
        reply = ai_reply_text(prompt)
        print(f"🖼️ /identify -> name={upload.filename} type={ctype} context={context!r} reply={reply[:120]}...")
        return {"filename": upload.filename, "reply": reply}
    except Exception as e:
        print(f"❌ Image identify error: {e}")
        return {"error": str(e), "ok": False}

# ---------- Twilio ----------
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
    print(f"📩 WhatsApp message from {From}: {Body}")
    if (NumMedia and NumMedia != "0") or MediaUrl0:
        prompt = f"Farmer says: {Body or '(no text)'}\nThey also sent an image: {MediaUrl0 or '(unavailable)'}"
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
