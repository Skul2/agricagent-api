from fastapi import APIRouter, Form, Response, UploadFile, File, HTTPException
from pydantic import BaseModel
import os, html, mimetypes, base64

# ---------- OpenAI client ----------
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    client = None

router = APIRouter()

# ---------- AI helper ----------
def ai_reply_text(prompt_text: str) -> str:
    """
    Handles pure text-based replies.
    """
    if not client:
        return "👋 I received your message. (AI disabled — please set OPENAI_API_KEY.)"
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AgriAgent, an intelligent agricultural assistant. "
                        "When given farmer text, respond clearly and practically, focusing "
                        "on crops, livestock, soil, weather, or pest management."
                    ),
                },
                {"role": "user", "content": prompt_text},
            ],
            max_tokens=500,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"AI error: {e}"


# ---------- Health check ----------
@router.get("/check")
def check():
    return {"ok": True, "status": "ok", "service": "AgriAgent API", "version": "2.0.0"}


# ---------- Text chat ----------
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


# ---------- Image Identification ----------
@router.post("/identify")
async def identify(
    file: UploadFile = File(None),
    image: UploadFile = File(None),
    context: str | None = Form(default=None)
):
    """
    Identifies plants, animals, insects, or crop issues from an uploaded image.
    Accepts image in 'file' (preferred) or 'image'.
    Optional 'context' (text hint) may include region, crop, or symptoms.
    """
    upload = file or image
    if not upload:
        raise HTTPException(status_code=400, detail="No image found. Use field 'file' or 'image'.")

    ctype = (upload.content_type or "").lower().strip()
    if not ctype.startswith("image/"):
        guessed, _ = mimetypes.guess_type(upload.filename or "")
        if not guessed or not guessed.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Invalid image type: {ctype or 'unknown'}")

    # Read image bytes and encode in Base64 for API
    img_bytes = await upload.read()
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    data_uri = f"data:{ctype};base64,{img_b64}"

    if not client:
        return {"ok": False, "error": "AI disabled — please set OPENAI_API_KEY."}

    # Define a strong, structured prompt
    prompt = (
        "You are AgriAgent, an expert agricultural assistant. "
        "Analyze the following image of a plant, insect, or animal and provide a clear, structured answer:\n\n"
        "1️⃣ **Crop/Plant/Animal:** Name or type\n"
        "2️⃣ **Likely Problem:** Disease, pest, or condition (if any)\n"
        "3️⃣ **Why:** Short explanation based on visible signs\n"
        "4️⃣ **Recommended Action:** Practical treatment or management advice\n"
        "5️⃣ **Preventive Tips:** How to avoid recurrence\n\n"
        "If healthy, say 'Healthy specimen detected.' Be specific but concise."
    )

    try:
        # Send image and text context to OpenAI Vision model
        response = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_text", "text": f"Farmer's context: {context or 'none provided'}"},
                        {"type": "input_image", "image_data": data_uri},
                    ],
                }
            ],
        )

        reply_text = response.output[0].content[0].text.strip()
        print(f"🖼️ /identify -> name={upload.filename} type={ctype} context={context!r} reply={reply_text[:120]}...")
        return {"ok": True, "filename": upload.filename, "reply": reply_text}

    except Exception as e:
        print(f"❌ Image identify error: {e}")
        return {"ok": False, "error": f"AI error: {e}"}


# ---------- Twilio Webhook ----------
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
