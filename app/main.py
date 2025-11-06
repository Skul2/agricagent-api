# app/main.py
import os
import base64
import tempfile
from typing import Optional
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx

app = FastAPI(title="AgricAgent API")

@app.get("/")
async def root():
    return {"status": "ok", "message": "AgricAgent API is running 🚜"}

@app.get("/routes")
async def routes():
    return {
        "routes": [
            "/",
            "/routes",
            "/chat",
            "/identify",
            "/docs",
            "/openapi.json",
        ]
    }

# ---------- CHAT ENDPOINT ----------
class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat(req: ChatRequest):
    """Simulated AI reply — replace with your actual OpenAI logic"""
    msg = req.message.lower()
    if "yellow" in msg:
        reply = """
**Possible Causes of Yellow Leaves**
1. Nutrient deficiency (especially Nitrogen)
2. Overwatering or poor drainage
3. Pests such as aphids or leaf miners

**What To Do**
- Check soil drainage and avoid overwatering
- Apply NPK fertilizer with high Nitrogen
- Inspect undersides of leaves for pests
"""
    else:
        reply = f"Your message was: {req.message}\nI'm still learning 🌱"
    return {"reply": reply.strip()}

# ---------- IDENTIFY ENDPOINT ----------
class IdentifyPayload(BaseModel):
    image_base64: Optional[str] = None

async def fake_vision_model(path: str):
    """Pretend AI detection"""
    name = os.path.basename(path).lower()
    if "cow" in name:
        return "Cow", "Detected a healthy cow 🐄"
    if "fish" in name:
        return "Fish", "Detected a fish 🐟"
    if "leaf" in name:
        return "Plant leaf", "Detected a crop leaf 🌿"
    return "Unknown", "Could not identify the image clearly."

@app.post("/identify")
async def identify(image: UploadFile = File(None), payload: IdentifyPayload = None):
    """
    Accepts either:
      - multipart/form-data with 'file'
      - JSON with base64 image
    """
    try:
        # Multipart file
        if image:
            suffix = os.path.splitext(image.filename or "image.jpg")[1]
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(await image.read())
            tmp.close()
            img_path = tmp.name
        # JSON base64
        elif payload and payload.image_base64:
            raw = base64.b64decode(payload.image_base64.split(",")[-1])
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp.write(raw)
            tmp.close()
            img_path = tmp.name
        else:
            return JSONResponse({"error": "No image provided."}, status_code=400)

        label, details = await fake_vision_model(img_path)
        return {"label": label, "details": details}
    except Exception as e:
        return JSONResponse({"error": f"Failed to analyze image: {e}"}, status_code=500)
