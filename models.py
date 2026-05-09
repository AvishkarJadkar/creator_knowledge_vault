from extensions import db
from datetime import datetime

# --- NOTE: User model removed as auth is now handled by Firebase ---

class Content(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), index=True, nullable=False) # Firebase UID
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    content_type = db.Column(db.String(50)) # tweet, blog, video_transcript, etc.
    source_url = db.Column(db.String(500))
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Embedding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey('content.id'), index=True, nullable=False)
    vector = db.Column(db.Text, nullable=False) # JSON string of float array

class SocialProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), index=True, nullable=False) # Firebase UID
    platform = db.Column(db.String(50), nullable=False)  # youtube, twitter, linkedin, instagram
    profile_url = db.Column(db.String(500), nullable=False)
    channel_id = db.Column(db.String(100), default="")  # YouTube channel ID for RSS
    last_synced_video = db.Column(db.String(200), default="")  # last imported video ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False) # Firebase UID
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
    user_id = db.Column(db.String(36), nullable=False) # Firebase UID
    fact = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(50), default="chat")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- NEW: Rate Limiting Models ---

class UserApiUsage(db.Model):
    """Tracks daily rolling window usage per user and API type."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), index=True, nullable=False)
    api_type = db.Column(db.String(50), index=True, nullable=False) # groq_chat, gemini_embed, etc.
    window_start = db.Column(db.DateTime, default=datetime.utcnow)
    call_count = db.Column(db.Integer, default=0)
    __table_args__ = (db.Index('ix_user_api_usage_composite', 'user_id', 'api_type'),)

class UserApiMinuteUsage(db.Model):
    """Tracks per-minute burst usage per user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    call_count = db.Column(db.Integer, default=0)
    minute_start = db.Column(db.DateTime, default=datetime.utcnow)
