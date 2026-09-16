import os
import requests
from dotenv import load_dotenv

load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

models_to_test = [
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro"
]

print("Testing Gemini API models...")
for m in models_to_test:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": "Hello, respond with JSON: {\"status\": \"ok\"}"}]}]
    }
    r = requests.post(url, json=payload)
    print(f"Model '{m}': Status {r.status_code}, Response: {r.text[:150]}")
