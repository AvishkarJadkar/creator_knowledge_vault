from extensions import db
from models import UserApiUsage, UserApiMinuteUsage
from datetime import datetime, timedelta

def check_and_increment(user_id, api_type, daily_limit=None, minute_limit=5):
    """
    Checks and increments API usage for a user.
    Returns (allowed: bool, message: str, retry_after: int)
    """
    now = datetime.utcnow()
    
    # 1. Burst Limit Check (Per Minute)
    min_usage = UserApiMinuteUsage.query.filter_by(user_id=user_id).first()
    if not min_usage:
        min_usage = UserApiMinuteUsage(user_id=user_id, minute_start=now, call_count=1)
        db.session.add(min_usage)
    else:
        if now - min_usage.minute_start > timedelta(minutes=1):
            min_usage.minute_start = now
            min_usage.call_count = 1
        else:
            if min_usage.call_count >= minute_limit:
                return False, "Too many requests. Please wait a minute.", 60
            min_usage.call_count += 1
            
    # 2. Daily Limit Check (Rolling 24h)
    if daily_limit:
        usage = UserApiUsage.query.filter_by(user_id=user_id, api_type=api_type).first()
        if not usage:
            usage = UserApiUsage(user_id=user_id, api_type=api_type, window_start=now, call_count=1)
            db.session.add(usage)
        else:
            if now - usage.window_start > timedelta(hours=24):
                usage.window_start = now
                usage.call_count = 1
            else:
                if usage.call_count >= daily_limit:
                    reset_time = usage.window_start + timedelta(hours=24)
                    wait_seconds = int((reset_time - now).total_seconds())
                    return False, f"Daily limit reached for {api_type.replace('_', ' ')}. Resets in {wait_seconds // 3600}h {(wait_seconds % 3600) // 60}m.", wait_seconds
                usage.call_count += 1
                
    db.session.commit()
    return True, "", 0

def roughly_count_tokens(text):
    """Simple token count approximation (1 token ~= 4 chars)."""
    if not text:
        return 0
    return len(text) // 4
