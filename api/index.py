import os
import sys

# Add project root to Python path so Flask app modules can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel serverless entry point — Vercel looks for the `app` variable
