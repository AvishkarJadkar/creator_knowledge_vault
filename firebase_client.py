import os
import requests
from dotenv import load_dotenv

load_dotenv()

FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY", "")

def _get_api_key():
    if not FIREBASE_API_KEY:
        raise ValueError("FIREBASE_API_KEY is missing from .env file")
    return FIREBASE_API_KEY

def sign_up(email, password, name=None):
    """Sign up a new user using Firebase Identity Toolkit REST API."""
    api_key = _get_api_key()
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
    
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    response = requests.post(url, json=payload)
    data = response.json()
    
    if "error" in data:
        raise Exception(data["error"]["message"])
        
    id_token = data.get("idToken")
    local_id = data.get("localId")
    
    # If name is provided, update the profile
    if name:
        update_url = f"https://identitytoolkit.googleapis.com/v1/accounts:update?key={api_key}"
        update_payload = {
            "idToken": id_token,
            "displayName": name,
            "returnSecureToken": True
        }
        update_response = requests.post(update_url, json=update_payload)
        update_data = update_response.json()
        if "error" in update_data:
            # Profile update failed, but user was created
            print(f"Warning: Failed to update display name: {update_data['error']['message']}")
    
    return {
        "session": {"access_token": id_token},
        "user": {"id": local_id, "user_metadata": {"name": name}}
    }

def sign_in_with_password(email, password):
    """Log in an existing user using Firebase Identity Toolkit REST API."""
    api_key = _get_api_key()
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    response = requests.post(url, json=payload)
    data = response.json()
    
    if "error" in data:
        raise Exception(data["error"]["message"])
        
    # We might need the display name. Let's get user data.
    id_token = data.get("idToken")
    local_id = data.get("localId")
    display_name = data.get("displayName") # signInWithPassword sometimes returns displayName
    
    if not display_name:
        # Fetch user data to get display name
        lookup_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}"
        lookup_payload = {"idToken": id_token}
        try:
            lookup_res = requests.post(lookup_url, json=lookup_payload).json()
            if "users" in lookup_res and len(lookup_res["users"]) > 0:
                display_name = lookup_res["users"][0].get("displayName")
        except:
            pass
            
    return {
        "session": {"access_token": id_token},
        "user": {"id": local_id, "user_metadata": {"name": display_name or "Creator"}}
    }

def sign_out():
    """Sign out is handled entirely client-side (session.clear()) with REST APIs."""
    pass
