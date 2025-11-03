import os
import requests
import base64

WEBHOOK_URL = "http://127.0.0.1:8000/webhook"
FROM_NUMBER = "whatsapp:+447469345866"
TEXT_MESSAGE = "Please analyze this image for AgricAgent."

IMAGE_FOLDER = "test_images"

def get_category_from_filename(filename):
    fname = filename.lower()
    if "crop" in fname:
        return "crop"
    elif "soil" in fname:
        return "soil"
    elif "animal" in fname:
        return "animal"
    elif "insect" in fname:
        return "insect"
    return "unknown"

def send_image(file_path):
    filename = os.path.basename(file_path)
    category = get_category_from_filename(filename)
    print(f"📤 Sending {category} image: {filename}")

    with open(file_path, "rb") as f:
        image_data = f.read()
        encoded = base64.b64encode(image_data).decode("utf-8")
        fake_media_url = f"data:image/jpeg;base64,{encoded}"

        data = {
            "From": FROM_NUMBER,
            "Body": f"{TEXT_MESSAGE} ({category})",
            "MediaUrl0": fake_media_url,
            "MediaContentType0": "image/jpeg"
        }

        try:
            response = requests.post(WEBHOOK_URL, data=data)
            print("Status Code:", response.status_code)
            print("Response Body:", response.text)
        except Exception as e:
            print("❌ Error sending request:", e)

if __name__ == "__main__":
    if not os.path.exists(IMAGE_FOLDER):
        print(f"❌ Folder '{IMAGE_FOLDER}' does not exist. Create it and add test images.")
    else:
        for file in os.listdir(IMAGE_FOLDER):
            if file.lower().endswith((".jpg", ".jpeg", ".png")):
                send_image(os.path.join(IMAGE_FOLDER, file))
