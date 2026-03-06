import os
from google import genai
from dotenv import load_dotenv
import math

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_embedding(text: str):
    """Generate a 768-dimensional embedding vector for the given text."""
    if not text or not text.strip():
        return None
    
    try:
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
        )
        return result.embeddings[0].values
    except Exception as e:
        print(f"DEBUG: Embedding Error: {type(e).__name__}: {e}")
        return None

def cosine_similarity(v1, v2):
    """Calculate the cosine similarity between two vectors."""
    if not v1 or not v2:
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
        
    return dot_product / (magnitude1 * magnitude2)
