import os
import requests

# =======================
# CONFIG
# =======================
WEBHOOK_URL = "http://127.0.0.1:8000/webhook"  # Your local FastAPI server
FROM_NUMBER = "whatsapp:+447469345866"        # Your testing WhatsApp number

# =======================
# IMAGE INPUT
# =======================
# Place your images in a folder named 'images' in the project root
IMAGES_DIR = "images"
TEXT_MESSAGE = "Hello AgriAgent, please analyze this image."

# =======================
# DETERMINE IMAGE TYPE
# =======================
def detect_type(filename: str) -> str:
    """Simple detection based on filename keywords"""
    fname = filename.lower()
    if "soil" in fname:
        return "soil"
    elif "crop" in fname or "plant" in fname:
        return "crop"
    elif "animal" in fname:
        return "animal"
    elif "insect" in fname or "bug" in fname:
        return "insect"
    else:
        return "unknown"

# =======================
# SEND REQUEST
# =======================
for file_name in os.listdir(IMAGES_DIR):
    local_path = os.path.join(IMAGES_DIR, file_name)
    if not os.path.isfile(local_path):
        continue

    image_type = detect_type(file_name)
    print(f"📤 Sending {image_type} image: {file_name}")

    try:
        with open(local_path, "rb") as f:
            files = {"MediaFile0": (f.name, f, "image/jpeg")}
            data = {
                "From": FROM_NUMBER,
                "Body": f"{TEXT_MESSAGE} [{image_type}]"
            }
            response = requests.post(WEBHOOK_URL, data=data, files=files)

        print("Status Code:", response.status_code)
        print("Response Body:", response.text)
        print("-" * 50)

    except Exception as e:
        print("❌ Error sending request:", e)
