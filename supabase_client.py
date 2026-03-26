import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_ANON_KEY", "")

# --- ERROR HANDLING: Check for placeholders or empty keys ---
is_placeholder = "your_supabase" in url or "your_supabase" in key or not url or not key

if is_placeholder:
    print("\n" + "="*60)
    print(" CRITICAL ERROR: Supabase Credentials Missing")
    print("="*60)
    print("Please update your .env file with your actual Supabase project")
    print("URL and Anon Key. You can find these in your Supabase Dashboard")
    print("under Settings -> API.")
    print("="*60 + "\n")
    # We set supabase to None so imports don't crash immediately,
    # but actual auth calls will fail gracefully later.
    supabase = None
else:
    try:
        supabase: Client = create_client(url, key)
    except Exception as e:
        print(f"\nERROR: Failed to initialize Supabase client: {e}")
        supabase = None
