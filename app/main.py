import os
import tempfile
import re
import base64
import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel
from twilio.twiml.messaging_response import MessagingResponse

from app.api_service import (
    handle_user_message,
    analyze_crop_image,
    analyze_soil_image,
    analyze_animal_image,
    analyze_insect_image,
)

# 🚀 Initialize FastAPI app
app = FastAPI(
    title="AgricAgent API",
    description="AI-powered agriculture assistant API for Flutter and WhatsApp integration.",
    version="1.0.0"
)

# --- Load Twilio credentials (optional for image download) ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
    print("⚠️ Warning: Twilio credentials not set. Image downloads from WhatsApp may fail.")


# --- Helper: Save base64 image ---
def _save_base64_image(data_url: str) -> str:
    """Decode base64 image data into a temporary file path."""
    match = re.match(r"data:(.*?);base64,(.*)", data_url)
    if not match:
        raise ValueError("Invalid base64 image data.")
    mime, b64 = match.groups()
    ext = mime.split("/")[-1] or "jpg"
    raw = base64.b64decode(b64)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
    tmp.write(raw)
    tmp.close()
    return tmp.name


# --- WhatsApp webhook endpoint ---
@app.post("/webhook", response_class=PlainTextResponse)
async def webhook(
    request: Request,
    From: str = Form(""),
    Body: str = Form(""),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
):
    """
    Twilio WhatsApp webhook or direct API POST.
    Handles both plain text and image-based messages.
    """
    print(f"📩 Incoming message from {From or 'Unknown'}: {Body[:80]}...")
    resp = MessagingResponse()
    msg = resp.message()
    body_lower = (Body or "").lower().strip()

    try:
        # --- If an image was included ---
        if MediaUrl0:
            print(f"🖼️ Received image: {MediaUrl0}")

            # Case 1: Local base64 image (from Flutter app)
            if MediaUrl0.startswith("data:image"):
                image_path = _save_base64_image(MediaUrl0)
                print(f"📁 Saved local base64 image at: {image_path}")

            # Case 2: Download from Twilio (production)
            else:
                try:
                    async with httpx.AsyncClient(
                        timeout=30.0,
                        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                        follow_redirects=True,
                    ) as client:
                        r = await client.get(MediaUrl0)
                        r.raise_for_status()
                        ext = (MediaContentType0 or "image/jpeg").split("/")[-1]
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
                        tmp.write(r.content)
                        tmp.close()
                        image_path = tmp.name
                        print(f"📁 Downloaded image saved to: {image_path}")
                except Exception as e:
                    print(f"❌ Error downloading image: {e}")
                    msg.body(f"⚠️ Could not download image: {e}")
                    return PlainTextResponse(str(resp), media_type="application/xml")

            # --- Route to appropriate analysis function ---
            if "soil" in body_lower:
                analysis = await analyze_soil_image(image_path)
            elif "animal" in body_lower or "livestock" in body_lower:
                analysis = await analyze_animal_image(image_path)
            elif "insect" in body_lower or "pest" in body_lower:
                analysis = await analyze_insect_image(image_path)
            else:
                analysis = await analyze_crop_image(image_path)

            msg.body(analysis)
            print("✅ Analysis complete and sent to user.")
            return PlainTextResponse(str(resp), media_type="application/xml")

        # --- Text-only message ---
        print("💬 Text message received — sending to AI handler.")
        reply = await handle_user_message(Body or "Hello")
        msg.body(reply)
        print("✅ Text reply sent.")
        return PlainTextResponse(str(resp), media_type="application/xml")

    except Exception as e:
        print("❌ Webhook error:", e)
        msg.body("⚠️ Sorry, I couldn't process your message right now.")
        return PlainTextResponse(str(resp), media_type="application/xml")


# --- Flutter App Chat Endpoint ---
class ChatRequest(BaseModel):
    message: str


@app.post("/chat", response_class=JSONResponse)
async def chat_endpoint(req: ChatRequest):
    """Flutter app endpoint — accepts a message and returns AI reply as JSON."""
    try:
        print(f"💬 Flutter chat received: {req.message}")
        reply = await handle_user_message(req.message)
        print(f"✅ Flutter chat reply: {reply[:100]}")
        return {"reply": reply}
    except Exception as e:
        print("❌ Chat endpoint error:", e)
        return JSONResponse({"error": "Failed to process message"}, status_code=500)


# --- Health check route ---
@app.get("/")
async def root():
    """Simple health check for ngrok or Render."""
    return {"status": "ok", "message": "AgricAgent API is running 🚜"}


# --- Entry point for Render (optional for local dev) ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
