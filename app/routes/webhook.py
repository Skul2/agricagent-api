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
    If Pillow is available, downscale longest side to <= max_side and JPEG re-encode
    to keep payload small & fast. Falls back to original bytes when PIL is absent.
    Returns (bytes, content_type).
    """
    if not _HAS_PIL:
        return img_bytes, "image/jpeg"
    try:
        im = Image.open(io.BytesIO(img_bytes))
        # Convert to RGB to avoid issues with PNG/alpha
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        # Downscale
        w, h = im.size
        longest = max(w, h)
        if longest > max_side:
            scale = max_side / float(longest)
            im = im.resize((int(w * scale), int(h * scale)))
        out = io.BytesIO()
        im.save(out, format="JPEG", quality=quality, optimize=True)
        return out.getvalue(), "image/jpeg"
    except Exception:
        # If anything goes wrong, just return original
        return img_bytes, "image/jpeg"

def _b64_data_url(image_bytes: bytes, content_type: str) -> str:
    ct = (content_type or "image/jpeg").lower().strip()
    if not ct.startswith("image/"):
        ct = "image/jpeg"
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{ct};base64,{b64}"

def _structured_prompt(filename: str, context: str | None) -> str:
    return (
        "You are AgriAgent, an expert agronomist for smallholder farmers. "
        "Carefully analyze the attached image (crop, leaf/fruit/stem/root, pests, animals, damage patterns). "
        "Be specific and avoid generic guesses. If uncertain, state 'Low confidence' and give the top 1–2 possibilities.\n\n"
        f"Filename: {filename or '(unknown)'}\n"
        f"Farmer context (may be empty): {context or '(none)'}\n\n"
        "Return the answer in exactly this format (no extra commentary):\n\n"
        "Crop/Plant or Animal: <one short name>\n"
        "Likely Problem: <one short diagnosis>\n"
        "Confidence: <High/Medium/Low>\n"
        "Why: <1–2 short sentences describing the visible cues>\n"
        "Recommended Action: <2–4 practical steps; safe, affordable>\n"
        "Preventive Tips: <2–3 short bullet points>\n"
    )

def _ai_text_only(prompt_text: str) -> str:
    if not _ok_openai():
        return "👋 I received your message. (AI disabled — set OPENAI_API_KEY.)"
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AgriAgent, an expert agronomist AI for farmers. "
                        "Provide clear, structured, practical answers."
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
        return "👋 I received your image. (AI disabled — set OPENAI_API_KEY.)"
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are AgriAgent, an expert agronomist AI for farmers. "
                    "Always return concise, specific, step-by-step guidance."
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
    return {"ok": True, "status": "ok", "service": "AgriAgent API", "version": "2.3.0"}

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
    True vision analysis with server-side compression:
    - Accepts 'file' (preferred) or 'image'
    - Optionally uses Pillow (if installed) to resize/re-encode before sending to OpenAI
    - Adds 'Confidence' field to the structured output
    """
    upload = file or image
    if not upload:
        raise HTTPException(status_code=400, detail="No image found. Use field 'file' or 'image'.")

    content_type = (upload.content_type or "").lower().strip()
    if not content_type.startswith("image/"):
        guessed, _ = mimetypes.guess_type(upload.filename or "")
        if not (guessed or "").startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Invalid image type: {content_type or 'unknown'}")
        content_type = guessed

    raw_bytes = await upload.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image was empty.")
    if len(raw_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max ~20MB).")

    # Compress (significantly reduces payload; avoids mobile timeouts)
    comp_bytes, comp_ct = _compress_image_bytes(raw_bytes, max_side=1600, quality=82)

    data_url = _b64_data_url(comp_bytes, comp_ct)
    prompt = _structured_prompt(upload.filename or "image", context)

    reply = _ai_vision(prompt, data_url)
    print(f"🖼️ /identify -> name={upload.filename} type={content_type} context={context!r} reply={reply[:140]}...")
    return {"filename": upload.filename, "reply": reply, "ok": True}

# ---------------------------
# Twilio WhatsApp webhook (text only for now)
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
    # (Optional) To do true vision with WhatsApp, fetch MediaUrl0 bytes server-side and reuse _ai_vision().
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
