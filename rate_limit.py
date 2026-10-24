from extensions import db
from models import UserApiUsage, UserApiMinuteUsage
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────
# TRIAL TIER LIMITS
# Central config — easy to swap for paid tiers later.
# Keys match the `api_type` strings used in check_and_increment().
# ─────────────────────────────────────────────────────────────
TRIAL_LIMITS = {
    "groq_chat": {
        "label": "Chat Credits",
        "limit": 50,
        "minute": 5,
        "icon": "message-circle",
    },
    "groq_remix": {
        "label": "Remix Credits",
        "limit": 30,
        "minute": 3,
        "icon": "repeat-2",
    },
    "gemini_embed": {
        "label": "Search & Embedding Credits",
        "limit": 200,
        "minute": 10,
        "icon": "search",
    },
    "gemini_explore": {
        "label": "Explore Credits",
        "limit": 20,
        "minute": 3,
        "icon": "compass",
    },
}


def check_and_increment(user_id, api_type, lifetime_limit=None, minute_limit=None):
    """
    Atomically checks and increments API usage for a user.
    """
    # Pull defaults from the central config if not overridden
    cfg = TRIAL_LIMITS.get(api_type, {})
    if lifetime_limit is None:
        lifetime_limit = cfg.get("limit")
    if minute_limit is None:
        minute_limit = cfg.get("minute", 5)

    now = datetime.utcnow()

    # ── 1. Burst limit (read-only check) ─────────────────────
    # We KEEP the minute limit to prevent abuse/infinite loops.
    # Nothing is mutated until every check below has passed: an earlier
    # version incremented first and called db.session.rollback() when a limit
    # was hit, which silently discarded unrelated pending work.
    min_usage = (
        UserApiMinuteUsage.query
        .filter_by(user_id=user_id, api_type=api_type)
        .with_for_update()
        .first()
    )

    in_current_minute = (
        min_usage is not None
        and (now - min_usage.minute_start) <= timedelta(minutes=1)
    )
    if in_current_minute and min_usage.call_count >= minute_limit:
        remaining = 60 - int((now - min_usage.minute_start).total_seconds())
        return False, "Too many requests. Please wait a minute.", max(remaining, 1)

    # ── 2. Lifetime limit (read-only check) ──────────────────
    usage = None
    if lifetime_limit:
        usage = (
            UserApiUsage.query
            .filter_by(user_id=user_id, api_type=api_type)
            .with_for_update()
            .first()
        )
        if usage and usage.call_count >= lifetime_limit:
            return (
                False,
                f"Lifetime credit limit reached for {cfg.get('label', api_type)}.",
                0,
            )

    # ── 3. All checks passed — increment and commit ──────────
    if not min_usage:
        min_usage = UserApiMinuteUsage(
            user_id=user_id,
            api_type=api_type,
            minute_start=now,
            call_count=1,
        )
        db.session.add(min_usage)
    elif not in_current_minute:
        min_usage.minute_start = now
        min_usage.call_count = 1
    else:
        min_usage.call_count += 1

    if lifetime_limit:
        if not usage:
            usage = UserApiUsage(
                user_id=user_id,
                api_type=api_type,
                window_start=now,
                call_count=1,
            )
            db.session.add(usage)
        else:
            usage.call_count += 1

    db.session.commit()
    return True, "", 0


def refund_usage(user_id, api_type):
    """Give back a credit after the provider call failed.

    Callers should invoke this whenever the upstream AI request raises, so a
    transient provider outage doesn't permanently burn a user's quota.
    """
    usage = (
        UserApiUsage.query
        .filter_by(user_id=user_id, api_type=api_type)
        .with_for_update()
        .first()
    )
    if usage and usage.call_count > 0:
        usage.call_count -= 1

    min_usage = (
        UserApiMinuteUsage.query
        .filter_by(user_id=user_id, api_type=api_type)
        .with_for_update()
        .first()
    )
    if min_usage and min_usage.call_count > 0:
        min_usage.call_count -= 1

    db.session.commit()


# ─────────────────────────────────────────────────────────────
# USAGE STATS (for the frontend quota display)
# ─────────────────────────────────────────────────────────────

def get_usage_stats(user_id):
    """
    Returns a dict of usage stats for every API type defined in TRIAL_LIMITS.
    Optimized to use a single database query.
    """
    stats = {}
    
    # Fetch all usage records for this user in one go
    all_usage = UserApiUsage.query.filter_by(user_id=user_id).all()
    usage_map = {u.api_type: u for u in all_usage}

    for api_type, cfg in TRIAL_LIMITS.items():
        limit = cfg["limit"]
        usage = usage_map.get(api_type)

        used = usage.call_count if usage else 0
        percent = int((used / limit) * 100) if limit else 0

        stats[api_type] = {
            "label": cfg["label"],
            "icon": cfg.get("icon", "activity"),
            "used": used,
            "limit": limit,
            "percent": min(percent, 100),
        }

    return stats


def get_remaining(user_id, api_type):
    """Quick helper — returns how many lifetime calls remain for a single API type."""
    cfg = TRIAL_LIMITS.get(api_type, {})
    limit = cfg.get("limit", 0)
    if not limit:
        return 0

    usage = UserApiUsage.query.filter_by(
        user_id=user_id, api_type=api_type
    ).first()

    if not usage:
        return limit

    return max(limit - usage.call_count, 0)


def roughly_count_tokens(text):
    """Simple token count approximation (1 token ~= 4 chars)."""
    if not text:
        return 0
    return len(text) // 4
