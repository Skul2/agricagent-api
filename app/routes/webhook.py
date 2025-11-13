from fastapi import APIRouter, Form, Response, UploadFile, File, HTTPException
from pydantic import BaseModel
import os, html, mimetypes, base64, io

# Try optional Pillow for server-side resize/compress
try:
    from PIL import Image  # type: ignore
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

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

def _compress_image_bytes(img_bytes: bytes, max_side: int = 1600, quality: int = 82) -> tuple[bytes, str]:
    """
    If Pillow is available, downscale longest side to <= max_side.
    Greatly reduces upload size, improves speed.
    """
    if not _HAS_PIL:
        return img_bytes, "image/jpeg"
    try:
        im = Image.open(io.BytesIO(img_bytes))
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")

        w, h = im.size
        longest = max(w, h)
        if longest > max_side:
            scale = max_side / float(longest)
            im = im.resize((int(w * scale)), int(h * scale))

        out = io.BytesIO()
        im.save(out, format="JPEG", quality=quality, optimize=True)
        return out.getvalue(), "image/jpeg"

    except Exception:
        return img_bytes, "image/jpeg"

def _b64_data_url(image_bytes: bytes, content_type: str) -> str:
    ct = (content_type or "image/jpeg").lower().strip()
    if not ct.startswith("image/"):
        ct = "image/jpeg"
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{ct};base64,{b64}"

def _structured_prompt(filename: str, context: str | None) -> str:
    """
    Vision prompt — now includes BENEFITS for plants/animals.
    """
    return (
        "You are AgriAgent, an expert agronomist for smallholder farmers. "
        "Analyze the attached image carefully: plant species, animals, insects, leaf symptoms, pests, diseases, deficiencies, soil issues.\n\n"
        f"Filename: {filename or '(unknown)'}\n"
        f"Farmer context (may be empty): {context or '(none)'}\n\n"

        "Return the answer *exactly in this structured format* (no extra commentary):\n\n"
        "Crop/Plant or Animal: <short name>\n"
        "Likely Problem: <diagnosis>\n"
        "Confidence: <High/Medium/Low>\n"
        "Why: <1–2 short visible clues>\n"
        "Recommended Action: <2–4 practical steps>\n"
        "Preventive Tips: <2–3 bullet points>\n"
        "Benefits: <2–4 short benefits about this plant/animal, when applicable>\n"
    )

def _ai_text_only(prompt_text: str) -> str:
    if not _ok_openai():
        return "👋 AI disabled — set OPENAI_API_KEY."
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AgriAgent, an agronomist AI. "
                        "Always reply cleanly, structured, and practical."
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
    if not _ok_openai():
        return "👋 AI disabled — set OPENAI_API_KEY."
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AgriAgent — identify plants, animals, insects, pests, "
                        "diseases, nutrient problems, and give actionable, structured guidance."
                    ),
                },
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
    return {"ok": True, "status": "ok", "service": "AgriAgent API", "version": "2.4.0"}

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
# Vision: IDENTIFY
# ---------------------------

@router.post("/identify")
async def identify(
    file: UploadFile = File(None),
    image: UploadFile = File(None),
    context: str | None = Form(default=None),
):
    upload = file or image
    if not upload:
        raise HTTPException(400, "No image found.")

    content_type = (upload.content_type or "").lower()
    if not content_type.startswith("image/"):
        guess, _ = mimetypes.guess_type(upload.filename or "")
        if not (guess or "").startswith("image/"):
            raise HTTPException(400, "Unsupported file type.")
        content_type = guess

    raw = await upload.read()
    if not raw:
        raise HTTPException(400, "Empty image.")
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(413, "Image too large (max ~20MB).")

    comp_bytes, comp_ct = _compress_image_bytes(raw, max_side=1600, quality=82)
    data_url = _b64_data_url(comp_bytes, comp_ct)

    prompt = _structured_prompt(upload.filename or "image", context)
    reply = _ai_vision(prompt, data_url)

    print(
        f"🖼️ /identify -> {upload.filename}, type={content_type}, "
        f"context={context!r}, reply={reply[:140]}..."
    )

    return {"filename": upload.filename, "reply": reply, "ok": True}

# ---------------------------
# WhatsApp webhook (text only)
# ---------------------------

def twiml_reply(text: str) -> Response:
    safe = html.escape(text, quote=True)
    xml = f'<?xml version="1.0"?><Response><Message>{safe}</Message></Response>'
    return Response(content=xml, media_type="application/xml")

@router.post("/webhook")
async def whatsapp_webhook(
    From: str = Form(default=""),
    Body: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: str | None = Form(default=None),
    MediaContentType0: str | None = Form(default=None),
):
    print(f"📩 WhatsApp: {From}: {Body}")

    if (NumMedia != "0") or MediaUrl0:
        prompt = f"Farmer says: {Body}\nThey sent an image: {MediaUrl0}"
    else:
        prompt = f"Farmer says: {Body}"

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
