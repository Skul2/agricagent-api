# app/main.py
import os
import base64
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="AgricAgent API")

@app.get("/")
async def root():
    return {"status": "ok", "message": "AgricAgent API is running 🚜"}

@app.get("/routes")
async def routes():
    return {
        "routes": [
            "/",
            "/chat",
            "/identify",
            "/routes",
            "/docs",
            "/openapi.json"
        ]
    }

# ---------- CHAT ----------
class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat(req: ChatRequest):
    msg = req.message.lower()
    if "yellow" in msg:
        reply = """
**Possible Causes of Yellow Leaves**
1. Nutrient deficiency (low Nitrogen)
2. Overwatering or poor drainage
3. Pests (aphids, leaf miners)

**What To Do**
- Check soil drainage, avoid overwatering
- Apply NPK fertilizer (20-10-10)
- Inspect underside of leaves for pests
"""
    else:
        reply = f"You said: {req.message}\nI'm here to help with your crops 🌱"
    return {"reply": reply.strip()}


# ---------- IDENTIFY ----------
@app.post("/identify")
async def identify(file: UploadFile = File(...)):
    """
    Receives an image from Flutter (camera/gallery)
    and returns a simple AI classification label.
    """
    try:
        suffix = os.path.splitext(file.filename or "image.jpg")[1]
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(await file.read())
        tmp.close()

        name = file.filename.lower()

        if "cow" in name:
            label, details = "Cow", "Detected a healthy cow 🐄"
        elif "goat" in name:
            label, details = "Goat", "Detected a goat 🐐"
        elif "fish" in name:
            label, details = "Fish", "Detected a fish 🐟"
        elif "leaf" in name or "plant" in name:
            label, details = "Plant leaf", "Detected a crop leaf 🌿"
        else:
            label, details = "Unknown", "Could not identify this image clearly."

        return {"ok": True, "label": label, "details": details}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {e}")
