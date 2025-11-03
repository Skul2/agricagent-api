# app/api_service.py
import os
import base64
import traceback
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()


# Load API key from env
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("⚠️ Warning: OPENAI_API_KEY not found in environment variables.")
client = OpenAI(api_key=api_key)


# ---------- Text only ----------
async def handle_user_message(message: str) -> str:
    """
    Handle a plain text message from the user.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AgriAgent — an expert agricultural assistant for farmers worldwide. "
                        "Provide short, clear, and practical answers with low-cost options."
                    ),
                },
                {"role": "user", "content": message},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ handle_user_message error:", e)
        print(traceback.format_exc())
        return "⚠️ Sorry, I couldn't process your message right now."


# ---------- Helpers ----------
def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def _image_message(prompt_text: str, b64_img: str):
    # OpenAI chat.completions with image requires {"type":"image_url","image_url":{"url":...}}
    return [
        {"type": "text", "text": prompt_text},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
    ]


# ---------- Image analyzers ----------
async def analyze_crop_image(image_path: str) -> str:
    try:
        b64_img = encode_image(image_path)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an agricultural expert diagnosing crop issues."},
                {"role": "user", "content": _image_message(
                    "Analyze this crop image. Give: 1) likely diagnosis, 2) 3 practical steps, 3) rough cost range, 4) when to escalate.",
                    b64_img
                )},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ analyze_crop_image error:", e)
        print(traceback.format_exc())
        return "⚠️ Sorry, I couldn’t analyze the crop image."

async def analyze_soil_image(image_path: str) -> str:
    try:
        b64_img = encode_image(image_path)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a soil scientist analyzing soil quality."},
                {"role": "user", "content": _image_message(
                    "Assess soil health from this image. Give 3 improvement steps and cost range.",
                    b64_img
                )},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ analyze_soil_image error:", e)
        print(traceback.format_exc())
        return "⚠️ Sorry, I couldn’t analyze the soil image."

async def analyze_animal_image(image_path: str) -> str:
    try:
        b64_img = encode_image(image_path)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a veterinary expert analyzing animal health."},
                {"role": "user", "content": _image_message(
                    "Analyze this animal for visible health issues and suggest what to do next.",
                    b64_img
                )},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ analyze_animal_image error:", e)
        print(traceback.format_exc())
        return "⚠️ Sorry, I couldn’t analyze the animal image."

async def analyze_insect_image(image_path: str) -> str:
    try:
        b64_img = encode_image(image_path)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an entomologist identifying crop pests."},
                {"role": "user", "content": _image_message(
                    "Identify this insect and recommend farmer-safe control measures.",
                    b64_img
                )},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ analyze_insect_image error:", e)
        print(traceback.format_exc())
        return "⚠️ Sorry, I couldn’t analyze the insect image."
