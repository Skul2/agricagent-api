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
    if not client:
        return "👋 I received your message. (AI disabled — please set OPENAI_API_KEY.)"
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are AgriAgent, an agronomist AI. "
                    "You must identify the likely crop/plant in the user's message or image context, "
                    "describe any visible or likely problem (pest, disease, nutrient, water, etc.), "
                    "and provide 2–3 clear, safe, region-neutral recommendations or treatments."
                )},
                {"role": "user", "content": prompt_text},
            ],
            max_tokens=400,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"AI error: {e}"

# ---------- Health ----------
@router.get("/check")
def check():
    return {"ok": True, "status": "ok", "service": "AgriAgent API", "version": "1.2.0"}

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
async def identify(file: UploadFile = File(None), image: UploadFile = File(None)):
    upload = file or image
    if not upload:
        raise HTTPException(status_code=400, detail="No image found; use 'file' or 'image'.")
    ctype = (upload.content_type or "").lower().strip()
    if not ctype.startswith("image/"):
        guessed, _ = mimetypes.guess_type(upload.filename or "")
        if not guessed or not guessed.startswith("image/"):
            raise HTTPException(status_code=400, detail="Invalid image type.")

    # read bytes (future vision use)
    await upload.read()

    prompt = (
        f"A farmer uploaded an image named '{upload.filename}'. "
        "Without seeing it directly, infer what crop or plant this likely shows, "
        "guess the possible issue (disease, pest, nutrient, water), "
        "and write:\n\n"
        "1️⃣ **Crop or Plant Name**\n"
        "2️⃣ **Problem Description**\n"
        "3️⃣ **Recommended Solution / Treatment**\n"
        "Be concise but specific and practical for smallholder farmers."
    )

    reply = ai_reply_text(prompt)
    print(f"🖼️ Received image: {upload.filename} ({ctype}) -> Reply: {reply[:80]}...")
    return {"filename": upload.filename, "reply": reply}

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
