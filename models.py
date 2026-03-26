from extensions import db
from datetime import datetime

# --- NOTE: User model removed as auth is now handled by Supabase ---

class Content(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False) # Supabase UUID
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    content_type = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


class Embedding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, nullable=False)
    vector = db.Column(db.Text, nullable=False)

class SocialProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False) # Supabase UUID
    platform = db.Column(db.String(50), nullable=False)  # youtube, twitter, linkedin, instagram
    profile_url = db.Column(db.String(500), nullable=False)
    channel_id = db.Column(db.String(100))  # YouTube channel ID for RSS
    last_synced_video = db.Column(db.String(200))  # last imported video ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False) # Supabase UUID
    title = db.Column(db.String(200), default="New Chat")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade="all, delete-orphan")

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Memory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False) # Supabase UUID
    fact = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(50), default="chat")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- NEW: Rate Limiting Models ---

class UserApiUsage(db.Model):
    """Tracks daily rolling window usage per user and API type."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    api_type = db.Column(db.String(50), nullable=False) # 'groq_chat', 'gemini_embed'
    call_count = db.Column(db.Integer, default=0)
    window_start = db.Column(db.DateTime, default=datetime.utcnow)

class UserApiMinuteUsage(db.Model):
    """Tracks per-minute burst usage per user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    call_count = db.Column(db.Integer, default=0)
    minute_start = db.Column(db.DateTime, default=datetime.utcnow)
