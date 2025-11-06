# app/main.py
import os
import base64
import tempfile
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

app = FastAPI(title="AgricAgent API")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Optional OpenAI Vision client
_openai_client = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print("⚠️ OpenAI unavailable:", e)
        _openai_client = None


@app.get("/")
async def root():
    return {"status": "ok", "message": "AgricAgent API is running 🚜"}


@app.get("/routes")
async def routes():
    return {"routes": ["/", "/chat", "/identify", "/routes", "/docs", "/openapi.json"]}


# ---------------- CHAT ----------------
class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat(req: ChatRequest):
    msg = (req.message or "").lower()

    if "mushroom" in msg:
        reply = (
            "<b>How to Plant Mushrooms 🍄</b><br>"
            "1️⃣ Obtain mushroom spores or spawn from a reliable supplier.<br>"
            "2️⃣ Prepare a substrate such as sawdust, straw, or compost.<br>"
            "3️⃣ Maintain high humidity (80–90%) and a temperature between 20–27°C.<br>"
            "4️⃣ Keep the area dark until the mycelium colonizes.<br>"
            "5️⃣ Harvest when caps open but before they flatten completely.<br><br>"
            "<b>Tip:</b> Avoid direct sunlight and ensure good airflow to prevent mold."
        )
    elif "yellow" in msg or "leaf" in msg:
        reply = (
            "<b>Yellow Leaves Causes 🌿</b><br>"
            "• Nitrogen deficiency<br>"
            "• Overwatering or poor drainage<br>"
            "• Pests (aphids, leaf miners)<br><br>"
            "<b>Solutions:</b><br>"
            "- Apply balanced NPK fertilizer (20-10-10).<br>"
            "- Allow soil to dry slightly between watering.<br>"
            "- Inspect undersides of leaves for pests and treat organically."
        )
    else:
        # General fallback
        if _openai_client:
            try:
                resp = _openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are AgricAgent, an AI expert in crops, soil, livestock, and pests. "
                                "Answer agricultural questions clearly with practical, step-by-step advice. "
                                "Use HTML <b>bold</b> tags for headings."
                            ),
                        },
                        {"role": "user", "content": req.message},
                    ],
                    temperature=0.5,
                )
                text = resp.choices[0].message.content.strip()
                return {"reply": text}
            except Exception as e:
                print("⚠️ AI chat fallback:", e)

        reply = (
            f"You said: {req.message}<br>"
            "I'm here to help with all crops, livestock, and soil management. "
            "Try asking about pest control, fertilizer, irrigation, or planting guides."
        )

    return {"reply": reply}


# ---------------- IDENTIFY ----------------
def _to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _simple_label(filename: str) -> tuple[str, str]:
    name = (filename or "").lower()
    if "leaf" in name or "plant" in name:
        return "Plant Leaf", "Detected a leaf. Possible nutrient stress or pest issue."
    if "cow" in name:
        return "Cow", "Detected a cow — check feed, water, and signs of illness."
    if "goat" in name:
        return "Goat", "Detected a goat — appears healthy."
    if "fish" in name:
        return "Fish", "Detected a fish — monitor water quality."
    return "Unknown", "Could not identify clearly — ensure good lighting and focus."


@app.post("/identify")
async def identify(file: Optional[UploadFile] = File(None), image_b64: Optional[str] = Form(None)):
    """Identify plants, animals, or farm items via image."""
    try:
        if file is not None:
            suffix = os.path.splitext(file.filename or "img.jpg")[1] or ".jpg"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(await file.read())
            tmp.close()
            tmp_path = tmp.name
        elif image_b64:
            img = base64.b64decode(image_b64.split(",")[-1])
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp.write(img)
            tmp.close()
            tmp_path = tmp.name
        else:
            raise HTTPException(status_code=400, detail="No image provided")

        # --- AI Vision ---
        if _openai_client:
            try:
                b64 = _to_b64(tmp_path)
                resp = _openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are AgricAgent, an AI agricultural vision expert. "
                                "Analyze the image and identify what it shows (plant, pest, animal, soil, etc). "
                                "Provide the species or object name, then clear 2–3 sentences of advice "
                                "for treatment, care, or management. Use HTML <b>bold</b> tags for the label."
                            ),
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "What is this image?"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                            ],
                        },
                    ],
                    temperature=0.4,
                )
                text = resp.choices[0].message.content.strip()
                return {"ok": True, "details": text}
            except Exception as e:
                print("⚠️ Vision failed:", e)

        # --- Fallback ---
        label, desc = _simple_label(file.filename if file else "image.jpg")
        html = f"<b>{label}</b><br>{desc}"
        return {"ok": True, "details": html}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image processing failed: {e}")
