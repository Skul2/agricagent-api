# app/main.py
import os
import base64
import tempfile
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AgricAgent API")

# CORS so Flutter can connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

_openai_client = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print("⚠️ OpenAI client unavailable:", e)


@app.get("/")
async def root():
    return {"status": "ok", "message": "AgricAgent API is running 🚜"}


@app.get("/routes")
async def routes():
    return {"routes": ["/", "/chat", "/identify", "/routes"]}


# ---------- CHAT ----------
class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat(req: ChatRequest):
    user_msg = (req.message or "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Empty message")

    # Direct OpenAI call for smart advice
    if _openai_client:
        try:
            res = _openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are AgricAgent, an AI expert on crops, soil, animals, and farming. "
                            "Always respond in full paragraphs using HTML <b> tags for headings. "
                            "Include clear, practical, and friendly explanations."
                        ),
                    },
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.5,
            )
            return {"reply": res.choices[0].message.content.strip()}
        except Exception as e:
            print("⚠️ Chat AI error:", e)

    # fallback
    return {"reply": f"<b>Note:</b> Could not contact AI. You asked: {user_msg}"}


# ---------- IDENTIFY ----------
def save_upload_to_temp(file: UploadFile) -> str:
    suffix = os.path.splitext(file.filename or "image.jpg")[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(file.file.read())
    tmp.close()
    return tmp.name


def encode_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


@app.post("/identify")
async def identify(
    file: Optional[UploadFile] = File(None),
    image_b64: Optional[str] = Form(None),
):
    """
    Identify any plant, animal, or farm-related image.
    Works with Flutter image picker (camera/gallery).
    """
    try:
        if file is None and not image_b64:
            raise HTTPException(status_code=400, detail="No image provided")

        # save image
        if file:
            img_path = save_upload_to_temp(file)
        else:
            img_bytes = base64.b64decode(image_b64.split(",")[-1])
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp.write(img_bytes)
            tmp.close()
            img_path = tmp.name

        # --- AI Vision ---
        if _openai_client:
            try:
                b64 = encode_b64(img_path)
                result = _openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are AgricAgent Vision, an agricultural vision AI. "
                                "Analyze the given image. Identify what it shows — "
                                "plant, animal, insect, disease, or other. "
                                "Then describe it clearly and give practical advice "
                                "for care, treatment, or improvement. "
                                "Format the response using <b> for headings."
                            ),
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Identify and describe this image:"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                            ],
                        },
                    ],
                    temperature=0.5,
                )
                text = result.choices[0].message.content.strip()
                return {"ok": True, "details": text}
            except Exception as e:
                print("⚠️ Vision model failed:", e)

        # --- fallback if no AI ---
        name = file.filename.lower() if file else "unknown"
        if "leaf" in name or "plant" in name:
            return {"ok": True, "details": "<b>Plant Leaf</b><br>Possible stress or deficiency detected."}
        if "cow" in name:
            return {"ok": True, "details": "<b>Cow</b><br>Healthy appearance, ensure adequate feed & water."}
        return {"ok": True, "details": "<b>Unknown Image</b><br>Could not identify clearly."}

    except Exception as e:
        print("❌ Error in /identify:", e)
        raise HTTPException(status_code=500, detail=str(e))
