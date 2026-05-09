import os
from google import genai
from dotenv import load_dotenv
import math
from rate_limit import check_and_increment

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_embedding(text: str, user_id: str = None):
    """Generate a 768-dimensional embedding vector for the given text."""
    if not text or not text.strip():
        return None
    
    # --- SECURITY: Max content size for embeddings ---
    if len(text) > 10000:
        print(f"DEBUG: Embedding text too long ({len(text)} characters). Truncating.")
        text = text[:10000]

    # --- RATE LIMITING: Per-user checks ---
    if user_id:
        allowed, msg, _ = check_and_increment(user_id, "gemini_embed")
        if not allowed:
            print(f"DEBUG: Rate limit exceeded for {user_id}: {msg}")
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
        
def generate_summary(text: str, user_id: str = None) -> str:
    """Synthesize a research report from multiple pieces of content."""
    if not text or not text.strip():
        return "No content available to summarize."
    
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
        # Use more robust model name identifier
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"DEBUG: Summary Error: {type(e).__name__}: {e}")
        return "Failed to generate research summary."
