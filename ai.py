import os
from google import genai
from dotenv import load_dotenv
import math
from rate_limit import check_and_increment, refund_usage

load_dotenv()

# --- MODEL CONFIGURATION ------------------------------------------------
# Verified against the live provider catalogs: the previously hardcoded
# `llama-3.3-70b-versatile`, `llama-3.1-8b-instant` and `gemini-2.0-flash`
# models have been retired and now fail with 404s. Override any of these with
# environment variables without touching the code.
GROQ_CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", "qwen/qwen3.8-27b")
GROQ_FAST_MODEL = os.getenv("GROQ_FAST_MODEL", "qwen/qwen3.8-27b")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")

_client = None

def get_client():
    """Lazy-initializes the Gemini client to avoid startup crashes if the key is missing."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            # We don't raise an error here so the app doesn't crash on startup.
            # Instead, we'll return None and handle it in the functions.
            return None
        _client = genai.Client(api_key=api_key)
    return _client

def get_embedding(text: str, user_id: str = None):
    """Generate a 768-dimensional embedding vector for the given text."""
    if not text or not text.strip():
        return None
    
    # --- SECURITY: Max content size for embeddings ---
    if len(text) > 10000:
        print(f"DEBUG: Embedding text too long ({len(text)} characters). Truncating.")
        text = text[:10000]

    # --- CONFIG CHECK: fail before consuming quota ---
    client = get_client()
    if not client:
        print("DEBUG: Gemini API Key missing. Skipping embedding.")
        return None

    # --- RATE LIMITING: Per-user checks ---
    if user_id:
        allowed, msg, _ = check_and_increment(user_id, "gemini_embed")
        if not allowed:
            print(f"DEBUG: Rate limit exceeded for {user_id}: {msg}")
            return None

    try:
        result = client.models.embed_content(
            model=GEMINI_EMBED_MODEL,
            contents=text,
        )
        return result.embeddings[0].values
    except Exception as e:
        if user_id:
            refund_usage(user_id, "gemini_embed")
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
        
def generate_summary(text: str, user_id: str = None) -> str:
    """Synthesize a research report from multiple pieces of content."""
    if not text or not text.strip():
        return "No content available to summarize."
    
    # --- CONFIG CHECK: fail before consuming quota ---
    client = get_client()
    if not client:
        return "⚠️ Gemini API Key missing. Please check your server configuration."

    # --- RATE LIMITING: Per-user checks ---
    if user_id:
        allowed, msg, _ = check_and_increment(user_id, "gemini_explore")
        if not allowed:
            return f"⚠️ {msg}"

    # --- SECURITY/STABILITY: Truncate input to avoid token limits ---
    # ~2,000 tokens / 8,000 characters is plenty for a synthesis of 5 posts
    MAX_CHARS = 8000
    if len(text) > MAX_CHARS:
        print(f"DEBUG: Truncating synthesis text from {len(text)} to {MAX_CHARS} characters.")
        text = text[:MAX_CHARS] + "..."

    prompt = f"""
    You are an expert research assistant. Analyze the following collection of posts and comments 
    on a specific topic and provide a comprehensive, structured summary.
    
    Focus on:
    1. Key themes and recurring ideas.
    2. Dominant opinions or consensus.
    3. Notable counter-points or controversial takes.
    4. Practical takeaways or advice mentioned.
    
    Format the output with clear headings and bullet points. Use a professional yet accessible tone.
    
    Content to synthesize:
    {text}
    
    Research Summary:
    """

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        if user_id:
            refund_usage(user_id, "gemini_explore")
        print(f"DEBUG: Summary Error: {type(e).__name__}: {e}")
        return "Failed to generate research summary."
