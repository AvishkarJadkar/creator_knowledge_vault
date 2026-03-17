import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    print("Testing gemini-1.5-flash-latest...")
    response = client.models.generate_content(
        model="gemini-1.5-flash-latest",
        contents="Hi",
    )
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

try:
    print("\nTesting models/gemini-1.5-flash-latest...")
    response = client.models.generate_content(
        model="models/gemini-1.5-flash-latest",
        contents="Hi",
    )
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
