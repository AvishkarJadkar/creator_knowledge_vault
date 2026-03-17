import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    print("Listing models...")
    for model in client.models.list():
        print(f"Name: {model.name}, Supported Actions: {model.supported_actions}")
except Exception as e:
    print(f"ERROR: {e}")
