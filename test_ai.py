import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    print("Testing gemini-2.0-flash...")
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Hello, say 'Test successful'",
    )
    print(response.text)
except Exception as e:
    print(f"FAILED gemini-2.0-flash: {e}")
    try:
        print("Testing gemini-1.5-flash...")
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents="Hello, say 'Test successful'",
        )
        print(response.text)
    except Exception as e2:
        print(f"FAILED gemini-1.5-flash: {e2}")
