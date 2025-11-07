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
    if not client:
        return "👋 I received your message. (AI disabled — please set OPENAI_API_KEY.)"
    try:
        completion = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": (
                    "You are AgriAgent, a concise and practical assistant for smallholder farmers. "
                    "Provide safe, actionable, context-specific guidance in 2–4 sentences."
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
# ==========================================================
@router.post("/chat")
async def chat(payload: ChatIn):
    """
    Alias for /message — older Flutter app builds use /chat
    """
    reply = ai_reply_text(f"Farmer says: {payload.text}")
    return {"reply": reply}

# ==========================================================
# 4️⃣ Image upload endpoint — app sends image for identification
# ==========================================================
@router.post("/identify")
async def identify(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")

    reply = ai_reply_text(
        f"A farmer uploaded an image named '{file.filename}'. "
        "Describe general guidance on analyzing crop or soil images safely."
    )
    return {"filename": file.filename, "reply": reply}

# =============================================
