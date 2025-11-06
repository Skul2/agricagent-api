# app/main.py
import os
import base64
import tempfile
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Optional OpenAI support
_openai_client = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as _e:
        _openai_client = None
        print("⚠️ OpenAI unavailable:", _e)

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


# ---------- CHAT ----------
class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat(req: ChatRequest):
    msg = (req.message or "").lower()
    if "yellow" in msg or "leaf" in msg:
        reply = (
            "**Possible Causes of Yellow Leaves**\n"
            "1. **Nutrient deficiency (Nitrogen)**\n"
            "2. **Overwatering / poor drainage**\n"
            "3. **Pests** (aphids, leaf miners)\n\n"
            "**What To Do**\n"
            "- Avoid overwatering; improve drainage\n"
            "- Apply balanced NPK (e.g., 20-10-10)\n"
            "- Inspect underside of leaves for pests"
        )
    else:
        reply = f"You said: {req.message}\nI’m here to help with your crops 🌱"
    return {"reply": reply}


# ---------- IDENTIFY ----------
def _b64_from_file(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _heuristic_label(filename: str) -> tuple[str, str]:
    name = (filename or "").lower()
    if any(k in name for k in ["cow", "cattle", "bovine"]):
        return "Cow", "Detected a cow 🐄"
    if "goat" in name:
        return "Goat", "Detected a goat 🐐"
    if "fish" in name or "tilapia" in name or "catfish" in name:
        return "Fish", "Detected a fish 🐟"
    if any(k in name for k in ["leaf", "plant", "maize", "corn", "cassava", "tomato", "rice"]):
        return "Plant leaf", "Detected a crop leaf 🌿"
    return "Unknown", "Could not identify this image clearly."


@app.post("/identify")
async def identify(
    file: Optional[UploadFile] = File(None),
    image_b64: Optional[str] = Form(None),
):
    """
    Accepts:
      - multipart form file under field name 'file' (camera/gallery)
      - OR base64 jpeg/png string via 'image_b64'
    Returns:
      { ok: bool, label: str, details: str }
    """
    try:
        # Save incoming image to a temp file
        if file is not None:
            suffix = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(await file.read())
            tmp.close()
            tmp_path = tmp.name
        elif image_b64:
            raw = base64.b64decode(image_b64.split(",")[-1])
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp.write(raw)
            tmp.close()
            tmp_path = tmp.name
        else:
            raise HTTPException(status_code=400, detail="No image provided. Send 'file' or 'image_b64'.")

        # If OpenAI is available, try vision classification
        if _openai_client:
            try:
                b64 = _b64_from_file(tmp_path)
                prompt = (
                    "You're an agricultural assistant. "
                    "Identify what the image shows (e.g., plant species/part, cow, goat, fish, insect). "
                    "Return a SHORT label and a one-sentence detail. "
                    "Format: LABEL: <label>; DETAILS: <details>."
                )
                resp = _openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                                },
                            ],
                        }
                    ],
                    temperature=0.2,
                )
                text = (resp.choices[0].message.content or "").strip()
                # Parse simple "LABEL: X; DETAILS: Y" if present
                label, details = "Unknown", "Could not identify this image clearly."
                if "LABEL:" in text:
                    parts = text.split("LABEL:", 1)[1]
                    if "; DETAILS:" in parts:
                        lbl, det = parts.split("; DETAILS:", 1)
                        label = lbl.strip().strip(":").strip()
                        details = det.strip().strip(".") + "."
                    else:
                        label = parts.strip()
                else:
                    # fallback to first line as label
                    first = text.splitlines()[0].strip()
                    if first:
                        label = first[:48]
                        details = text
                if not label:
                    label = "Unknown"
                if not details:
                    details = "No details."
                return {"ok": True, "label": label, "details": details}
            except Exception as e:
                print("⚠️ OpenAI vision error:", e)
                # Fall through to heuristic

        # Heuristic fallback (filename only)
        inferred_label, inferred_details = _heuristic_label(file.filename if file else "image.jpg")
        return {"ok": True, "label": inferred_label, "details": inferred_details}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {e}")
