import requests
import os
from dotenv import load_dotenv
from requests.exceptions import Timeout

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "https://agricagent-api-1.onrender.com")
TIMEOUT = 60  # seconds

class ApiService:
    @staticmethod
    def send_message(message: str):
        try:
            response = requests.post(
                f"{API_BASE_URL}/chat",
                json={"message": message},
                timeout=TIMEOUT,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("reply", "No reply received.")
            else:
                return f"Server error: {response.status_code}"
        except Timeout:
            return "⏱️ Server took too long to respond (timeout)."
        except Exception as e:
            return f"Error: {str(e)}"

    @staticmethod
    def send_image(file_path: str):
        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                response = requests.post(
                    f"{API_BASE_URL}/identify", files=files, timeout=TIMEOUT
                )
            if response.status_code == 200:
                data = response.json()
                return data.get("reply", "No analysis result.")
            else:
                return f"Server error: {response.status_code}"
        except Timeout:
            return "⏱️ Server took too long to analyze the image."
        except Exception as e:
            return f"Error: {str(e)}"
