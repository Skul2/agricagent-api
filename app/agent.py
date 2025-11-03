import os
import io
import asyncio
from dotenv import load_dotenv
from twilio.rest import Client
from app.db import save_message
from PIL import Image

load_dotenv()

# === Twilio Credentials ===
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# === OpenAI API Key ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize Twilio Client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def format_whatsapp_number(number: str) -> str:
    """Ensure the number is in correct WhatsApp format."""
    number = number.strip()
    if not number.startswith("whatsapp:"):
        if not number.startswith("+"):
            number = f"+{number.lstrip('+')}"
        number = f"whatsapp:{number}"
    return number


def send_whatsapp_sync(to_number: str, text: str):
    """Send WhatsApp message via Twilio synchronously."""
    try:
        to_number = format_whatsapp_number(to_number)
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to_number,
            body=text
        )
        print(f"✅ WhatsApp message sent to {to_number}: SID {message.sid}")
    except Exception as e:
        print("❌ Failed to send WhatsApp message:", e)


async def call_openai_system(user_text: str, user_meta: dict = None):
    """Call OpenAI API to generate a smart response."""
    import httpx

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    prompt = (
        f"User says: {user_text}\n"
        "Provide:\n"
        "1) One-sentence diagnosis\n"
        "2) 3 practical steps the farmer can take today\n"
        "3) Estimated cost range (in Naira)\n"
        "4) When to consult an agricultural extension officer"
    )

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are AgriAgent — an agricultural assistant for smallholder farmers in Nigeria. "
                    "Provide clear, practical, and low-cost advice using simple language."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 400,
        "temperature": 0.2,
    }

    async with httpx.AsyncClient(timeout=30.0) as client_http:
        try:
            response = await client_http.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print("❌ OpenAI API call failed:", e)
            return None


async def handle_user_message(user, text: str):
    """Process a user text message."""
    meta = {"phone": user.phone, "language": getattr(user, "language", "en")}

    try:
        ai_reply = await call_openai_system(text, meta)
        if not ai_reply:
            ai_reply = "Sorry, I couldn't process your request right now."
    except Exception as e:
        print("❌ Error generating AI response:", e)
        ai_reply = "Sorry, I couldn't process your request right now."

    # Save AI message in DB
    try:
        await save_message(user_id=user.id, role="agent", text=ai_reply)
    except Exception as e:
        print("❌ Failed to save message:", e)

    # Send AI message via WhatsApp
    try:
        await asyncio.to_thread(send_whatsapp_sync, user.phone, ai_reply)
    except Exception as e:
        print("❌ Failed to send WhatsApp message:", e)

    return ai_reply


# === Optional Image Analysis ===
async def analyze_crop_image(file_bytes: bytes, filename: str = "uploaded_crop.jpg"):
    """Analyze a crop image and return AI advice."""
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()

        prompt = f"Analyze this crop image for pests, diseases, or nutrient deficiencies: {filename}"
        advice = await call_openai_system(prompt)
        return advice or "Could not analyze the crop image."
    except Exception as e:
        print("❌ analyze_crop_image error:", e)
        return "Failed to process the crop image."


async def analyze_soil_image(file_bytes: bytes, filename: str = "uploaded_soil.jpg"):
    """Analyze a soil image and provide advice for soil fertility."""
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()

        prompt = f"Analyze this soil image and give fertility improvement advice: {filename}"
        advice = await call_openai_system(prompt)
        return advice or "Could not analyze the soil image."
    except Exception as e:
        print("❌ analyze_soil_image error:", e)
        return "Failed to process the soil image."
