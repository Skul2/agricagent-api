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


# ----------------- CHAT -----------------
class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat(req: ChatRequest):
    msg = (req.message or "").lower()
    if "yellow" in msg or "leaf" in msg:
        reply = (
            "<b>Possible Causes of Yellow Leaves</b>\n"
            "1. Nutrient deficiency (Nitrogen)\n"
            "2. Overwatering or poor drainage\n"
            "3. Pests (aphids, leaf miners)\n\n"
            "<b>What To Do</b>\n"
            "- Avoid overwatering; ensure soil drains well\n"
            "- Apply NPK fertilizer (20-10-10)\n"
            "- Inspect leaves for insects under the surface"
        )
    else:
        reply = (
            f"You said: {req.message}\n"
            "I’m here to help with your crops 🌿. "
            "Try asking about a specific problem (e.g., yellowing, pests, watering schedule)."
        )
    return {"reply": reply}


# ----------------- IDENTIFY -----------------
def _to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _simple_label(filename: str) -> tuple[str, str]:
    name = (filename or "").lower()
    if "leaf" in name or "plant" in name:
        return "Leaf", "Detected a plant leaf showing some stress or discoloration."
    if "cow" in name:
        return "Cow", "Detected a cow — appears healthy and active."
    if "goat" in name:
        return "Goat", "Detected a goat — appears healthy."
    if "fish" in name:
        return "Fish", "Detected a fish — check water clarity and oxygenation."
    return "Unknown", "Could not identify this image clearly."


@app.post("/identify")
async def identify(file: Optional[UploadFile] = File(None), image_b64: Optional[str] = Form(None)):
    """
    Accepts camera/gallery uploads or base64 strings.
    Returns an AI label and description.
    """
    try:
        # --- Save incoming image ---
        if file is not None:
            suffix = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(await file.read())
            tmp.close()
            tmp_path = tmp.name
        elif image_b64:
            imgdata = base64.b64decode(image_b64.split(",")[-1])
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp.write(imgdata)
            tmp.close()
            tmp_path = tmp.name
        else:
            raise HTTPException(status_code=400, detail="No image provided")

        # --- If OpenAI Vision available ---
        if _openai_client:
            try:
                b64 = _to_b64(tmp_path)
                resp = _openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "You are an agricultural vision assistant. "
                                        "Analyze the photo and describe what you see: plant, leaf, animal, or other. "
                                        "Return a short label and a 2–3 sentence explanation. "
                                        "Use HTML bold tags for headings (e.g. <b>Leaf</b>)."
                                    ),
                                },
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                            ],
                        }
                    ],
                    temperature=0.4,
                )
                text = resp.choices[0].message.content.strip()
                if not text:
                    raise ValueError("Empty AI reply")
                return {"ok": True, "label": "AI", "details": text}
            except Exception as e:
                print("⚠️ OpenAI vision error:", e)
                pass  # fall back

        # --- Fallback heuristic ---
        label, details = _simple_label(file.filename if file else "image.jpg")
        html = f"<b>{label}</b>\n{details}"
        return {"ok": True, "label": label, "details": html}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {e}")
