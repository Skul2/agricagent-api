from fastapi import APIRouter, Form, Response, UploadFile, File, HTTPException
from pydantic import BaseModel
import os, html, mimetypes, base64, io

try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    client = None

router = APIRouter()

# ---------------------------
# Helpers
# ---------------------------

def _ok_openai() -> bool:
    return bool(client and os.getenv("OPENAI_API_KEY"))

def _b64_data_url(image_bytes: bytes, content_type: str) -> str:
    """
    Build a data URL OpenAI can read for vision:
    data:<mime>;base64,<b64>
    """
    # Normalize MIME
    ct = (content_type or "image/jpeg").lower().strip()
    if not ct.startswith("image/"):
        ct = "image/jpeg"
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{ct};base64,{b64}"

def _structured_prompt(filename: str, context: str | None) -> str:
    """
    Strong, structured instructions (model will SEE the image).
    """
    return (
        "You are AgriAgent, an expert agronomist for smallholder farmers. "
        "Analyze the attached image carefully (crop, leaf, fruit, stem, insect/animal, symptoms, damage patterns). "
        "Then provide a practical, concise, **actionable** answer.\n\n"
        f"Filename: {filename or '(unknown)'}\n"
        f"Farmer context (may be empty): {context or '(none)'}\n\n"
        "Return your answer in **exactly** this format (no extra commentary):\n\n"
        "Crop/Plant or Animal: <one short name>\n"
        "Likely Problem: <1 short diagnosis>\n"
        "Why: <1–2 short sentences describing the relevant visual cues>\n"
        "Recommended Action: <2–4 practical steps; safe, affordable; include treatment name if appropriate>\n"
        "Preventive Tips: <2–3 short bullet points>\n"
    )

def _ai_text_only(prompt_text: str) -> str:
    """Text-only completion for /chat and WhatsApp webhook."""
    if not _ok_openai():
        return "👋 I received your message. (AI disabled — please set OPENAI_API_KEY.)"
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AgriAgent, an expert agronomist AI for farmers. "
                        "Provide clear, structured, and practical answers."
                    ),
                },
                {"role": "user", "content": prompt_text},
            ],
            max_tokens=500,
            temperature=0.2,
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as e:
        return f"AI error: {e}"

def _ai_vision(prompt_text: str, image_data_url: str) -> str:
    """Vision completion using chat.completions with image content."""
    if not _ok_openai():
        return "👋 I received your image. (AI disabled — please set OPENAI_API_KEY.)"
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are AgriAgent, an expert agronomist AI for farmers. "
                    "Always return concise, safe, step-by-step practical guidance."
                )},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ],
            max_tokens=700,
            temperature=0.2,
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as e:
        return f"AI error: {e}"

# ---------------------------
# Health
# ---------------------------

@router.get("/check")
def check():
    return {"ok": True, "status": "ok", "service": "AgriAgent API", "version": "2.2.0"}

# ---------------------------
# Text endpoints
# ---------------------------

class ChatIn(BaseModel):
    text: str | None = None
    message: str | None = None

@router.post("/chat")
async def chat(payload: dict):
    text = (payload.get("text") or payload.get("message") or "").strip()
    reply = _ai_text_only(f"Farmer says: {text}")
    return {"reply": reply}

@router.post("/message")
async def message(payload: ChatIn):
    text = (payload.text or payload.message or "").strip()
    reply = _ai_text_only(f"Farmer says: {text}")
    return {"reply": reply}

# ---------------------------
# Vision endpoint
# ---------------------------

@router.post("/identify")
async def identify(
    file: UploadFile = File(None),
    image: UploadFile = File(None),
    context: str | None = Form(default=None),
):
    """
    True vision analysis:
    - Accepts image in 'file' (preferred) or 'image'
    - Optional 'context' field (crop/location/symptoms)
    - Sends a data URL (base64) to GPT-4o-mini for pixel-level analysis
    """
    upload = file or image
    if not upload:
        raise HTTPException(status_code=400, detail="No image found. Use field 'file' or 'image'.")

    # Validate content type or try to guess
    content_type = (upload.content_type or "").lower().strip()
    if not content_type.startswith("image/"):
        guessed, _ = mimetypes.guess_type(upload.filename or "")
        if not (guessed or "").startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Invalid image type: {content_type or 'unknown'}")
        content_type = guessed

    # Read image bytes (limit ~10MB safety)
    img_bytes = await upload.read()
    if not img_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image was empty.")
    if len(img_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max ~10MB).")

    # Build data URL for OpenAI
    data_url = _b64_data_url(img_bytes, content_type)
    prompt = _structured_prompt(upload.filename or "image", context)

    reply = _ai_vision(prompt, data_url)
    print(f"🖼️ /identify -> name={upload.filename} type={content_type} context={context!r} reply={reply[:140]}...")
    return {"filename": upload.filename, "reply": reply, "ok": True}

# ---------------------------
# Twilio WhatsApp webhook
# ---------------------------

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
    # NOTE: Twilio sends media as a URL; to do vision here, you'd fetch the bytes server-side.
    if (NumMedia and NumMedia != "0") or MediaUrl0:
        prompt = f"Farmer says: {Body or '(no text)'}\nThey also sent an image: {MediaUrl0 or '(unavailable)'}"
    else:
        prompt = f"Farmer says: {Body or '(no text)'}"
    reply = _ai_text_only(prompt)
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
