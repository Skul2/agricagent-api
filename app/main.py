import os
import base64
import httpx
from fastapi import FastAPI, Depends, Form, UploadFile, File
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.requests import Request
from dotenv import load_dotenv
from typing import Optional

from .database import engine, Base, get_db
from .models import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .utils.file_io import decode_data_url, save_bytes_to_file
from .agent import analyze_image_with_openai, infer_category_from_text

load_dotenv()

app = FastAPI(title="AgriAgent API", version="0.2.0")

# ============================================
# STARTUP EVENT: Create tables automatically
# ============================================
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ============================================
# HEALTH CHECK
# ============================================
@app.get("/", response_class=PlainTextResponse)
async def health():
    return "AgriAgent API up and running ✅"

# ============================================
# WEBHOOK: Handles Twilio and App uploads
# ============================================
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
    This route handles both:
      1. Twilio form POSTs (MediaUrl0, MediaContentType0)
      2. Direct uploads from Flutter (multipart file)
    """

    saved_path = None
    media_type = MediaContentType0
    image_url_for_model = None

    # ----------------------------
    # CASE 1: Direct upload (Flutter app)
    # ----------------------------
    if file is not None:
        content = await file.read()
        ext = os.path.splitext(file.filename)[-1].replace(".", "") or "jpg"
        saved_path = save_bytes_to_file(content, ext_hint=ext)
        mime = media_type or f"image/{ext}"
        data_url = f"data:{mime};base64,{base64.b64encode(content).decode()}"
        image_url_for_model = data_url
        media_type = mime

    # ----------------------------
    # CASE 2: Twilio sends MediaUrl0 (URL or base64 data)
    # ----------------------------
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
                    ext = "jpg" if "png" not in ct else "png"
                    saved_path = save_bytes_to_file(r.content, ext_hint=ext)
                    media_type = ct
                image_url_for_model = MediaUrl0
            except Exception as e:
                print(f"⚠️ Failed to fetch media: {e}")
                image_url_for_model = None

    # ----------------------------
    # Analyze image (if any)
    # ----------------------------
    if image_url_for_model:
        analysis = analyze_image_with_openai(Body, image_url_for_model)
    else:
        analysis = (
            "No image received. Please send a clear photo of your crop, soil, or insect for analysis."
        )

    # ----------------------------
    # Infer category & save to DB
    # ----------------------------
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

    # ----------------------------
    # Response for both App & Twilio
    # ----------------------------
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

# ============================================
# GET /messages: For Admin & Debug
# ============================================
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
