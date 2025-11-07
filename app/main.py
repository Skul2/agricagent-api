import os
import base64
import httpx
from fastapi import FastAPI, Depends, Form, UploadFile, File
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.requests import Request
from dotenv import load_dotenv
from typing import Optional

# ✅ Absolute imports (Render-safe)
from app.database import engine, Base, get_db
from app.models import Message
from app.utils.file_io import decode_data_url, save_bytes_to_file
from app.agent import analyze_image_with_openai, infer_category_from_text

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# ===================================================
# ENVIRONMENT
# ===================================================
load_dotenv()

app = FastAPI(title="AgriAgent API", version="0.2.1")

# ===================================================
# STARTUP EVENT — auto-create tables
# ===================================================
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ===================================================
# HEALTH CHECK
# ===================================================
@app.get("/", response_class=PlainTextResponse)
async def health():
    return "AgriAgent API up and running ✅"

# ===================================================
# WEBHOOK — supports Twilio & Flutter uploads
# ===================================================
@app.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(default=None),
    Body: str = Form(default=""),
    MediaUrl0: str = Form(default=None),
    MediaContentType0: str = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Handles both:
      1. Twilio-style WhatsApp messages (MediaUrl0 / MediaContentType0)
      2. Direct uploads from Flutter (multipart file)
    """

    saved_path = None
    media_type = MediaContentType0
    image_url_for_model = None

    # ---------------------------------------------------
    # CASE 1: Flutter app — user directly uploads a file
    # ---------------------------------------------------
    if file is not None:
        content = await file.read()
        ext = os.path.splitext(file.filename)[-1].replace(".", "") or "jpg"
        saved_path = save_bytes_to_file(content, ext_hint=ext)
        mime = media_type or f"image/{ext}"
        data_url = f"data:{mime};base64,{base64.b64encode(content).decode()}"
        image_url_for_model = data_url
        media_type = mime

    # ---------------------------------------------------
    # CASE 2: Twilio webhook — remote MediaUrl
    # ---------------------------------------------------
    elif MediaUrl0:
        decoded = decode_data_url(MediaUrl0)
        if decoded:
            raw, mime, ext = decoded
            saved_path = save_bytes_to_file(raw, ext_hint=ext)
            image_url_for_model = MediaUrl0
            media_type = mime
        else:
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    r = await client.get(MediaUrl0)
                    r.raise_for_status()
                    ct = r.headers.get("content-type", "image/jpeg")
                    ext = "png" if "png" in ct else "jpg"
                    saved_path = save_bytes_to_file(r.content, ext_hint=ext)
                    media_type = ct
                image_url_for_model = MediaUrl0
            except Exception as e:
                print(f"⚠️ Failed to fetch media: {e}")
                image_url_for_model = None

    # ---------------------------------------------------
    # ANALYSIS — call OpenAI Vision
    # ---------------------------------------------------
    if image_url_for_model:
        analysis = analyze_image_with_openai(Body, image_url_for_model)
    else:
        analysis = (
            "No image received. Please send or capture a clear photo of your crop, soil, or insect."
        )

    # ---------------------------------------------------
    # CATEGORY DETECTION & SAVE TO DATABASE
    # ---------------------------------------------------
    category = infer_category_from_text(Body)

    msg = Message(
        from_number=From,
        body=Body,
        media_type=media_type,
        media_local_path=saved_path,
        category=category,
        analysis=analysis,
    )

    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    # ---------------------------------------------------
    # RESPONSE — works for Twilio & Flutter
    # ---------------------------------------------------
    return JSONResponse(
        {
            "status": "ok",
            "message_id": msg.id,
            "from": From,
            "category": category,
            "analysis": analysis[:1000],
            "saved_path": saved_path,
        }
    )

# ===================================================
# GET /messages — for Admin & Debug
# ===================================================
@app.get("/messages")
async def list_messages(db: AsyncSession = Depends(get_db), limit: int = 50):
    q = await db.execute(select(Message).order_by(Message.id.desc()).limit(limit))
    rows = q.scalars().all()
    return [
        {
            "id": m.id,
            "from_number": m.from_number,
            "body": m.body,
            "media_type": m.media_type,
            "media_local_path": m.media_local_path,
            "category": m.category,
            "analysis": m.analysis,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in rows
    ]
