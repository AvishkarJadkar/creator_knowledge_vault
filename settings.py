import re
import feedparser
import urllib.request
import os
import json
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, g
from extensions import db
from models import SocialProfile, Content, Embedding
from youtube_utils import get_youtube_transcript
from ai import get_embedding
from rate_limit import get_usage_stats

settings_bp = Blueprint("settings", __name__)


def resolve_channel_id(url):
    """Resolve a YouTube URL to a channel ID by fetching the page and extracting it."""
    try:
        # If already a channel ID URL
        match = re.search(r'youtube\.com/channel/(UC[\w-]+)', url)
        if match:
            return match.group(1)

        # For handles (@username) or custom URLs, fetch the page to find channel ID
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        # Look for channel ID in the page source
        match = re.search(r'"channelId":"(UC[\w-]+)"', html)
        if match:
            return match.group(1)

        match = re.search(r'channel/(UC[\w-]+)', html)
        if match:
            return match.group(1)

        # Try externalId
        match = re.search(r'"externalId":"(UC[\w-]+)"', html)
        if match:
            return match.group(1)

    except Exception as e:
        print(f"Error resolving channel ID: {e}")

    return None


@settings_bp.route("/settings", methods=["GET"])
def settings():
    if not g.user_id:
        return redirect(url_for("auth.login"))

    profiles = SocialProfile.query.filter_by(user_id=g.user_id).all()
    return render_template("settings.html", profiles=profiles)


@settings_bp.route("/onboarding", methods=["GET"])
def onboarding():
    if not g.user_id:
        return redirect(url_for("auth.login"))
    
    # If they already have a profile, skip onboarding
    existing = SocialProfile.query.filter_by(user_id=g.user_id).first()
    if existing:
        return redirect(url_for("dashboard"))
        
    return render_template("onboarding.html")


@settings_bp.route("/settings/add-profile", methods=["POST"])
def add_profile():
    if not g.user_id:
        return redirect(url_for("auth.login"))

    platform = request.form.get("platform", "").strip()
    profile_url = request.form.get("profile_url", "").strip()

    # --- SECURITY: Validate platform against whitelist ---
    allowed_platforms = {"youtube", "twitter", "linkedin", "instagram"}
    if platform not in allowed_platforms:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "Invalid platform selected"})
        flash("Invalid platform selected", "error")
        return redirect(url_for("settings.settings"))

    if not profile_url:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "Please enter a profile URL"})
        flash("Please enter a profile URL", "error")
        return redirect(url_for("settings.settings"))

    # --- SECURITY: Validate URL format and length ---
    if len(profile_url) > 500 or not profile_url.startswith("https://"):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "Please enter a valid HTTPS profile URL"})
        flash("Please enter a valid HTTPS profile URL", "error")
        return redirect(url_for("settings.settings"))


    # Check for duplicate
    existing = SocialProfile.query.filter_by(
        user_id=g.user_id,
        platform=platform,
        profile_url=profile_url
    ).first()
    if existing:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "This profile is already linked"})
        flash("This profile is already linked", "error")
        return redirect(url_for("settings.settings"))

    channel_id = None
    if platform == "youtube":
        channel_id = resolve_channel_id(profile_url)
        if not channel_id:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"status": "error", "message": "Could not detect YouTube channel. Make sure the URL is correct."})
            flash("Could not detect YouTube channel. Make sure the URL is correct.", "error")
            return redirect(url_for("settings.settings"))

    profile = SocialProfile(
        user_id=g.user_id,
        platform=platform,
        profile_url=profile_url,
        channel_id=channel_id or "",
        last_synced_video="",
    )
    db.session.add(profile)
    db.session.commit()
    # --- AJAX Response for Success ---
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "status": "success",
            "message": f"{platform.title()} profile linked successfully!",
            "profile": {
                "id": profile.id,
                "platform": profile.platform,
                "profile_url": profile.profile_url
            }
        })

    flash(f"{platform.title()} profile linked successfully!", "success")
    return redirect(url_for("settings.settings"))


@settings_bp.route("/settings/remove-profile/<int:profile_id>", methods=["POST"])
def remove_profile(profile_id):
    if not g.user_id:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        return redirect(url_for("auth.login"))

    profile = SocialProfile.query.get_or_404(profile_id)
    if profile.user_id != g.user_id:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        return redirect(url_for("settings.settings"))

    db.session.delete(profile)
    db.session.commit()
    
    # --- AJAX Response ---
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "success", "message": "Profile removed"})
        
    flash("Profile removed", "success")
    return redirect(url_for("settings.settings"))


import threading
from flask import current_app

def run_sync_in_background(app, profile_id, user_id):
    """Wrapper to run sync in a separate thread with the app context."""
    with app.app_context():
        profile = SocialProfile.query.get(profile_id)
        if profile:
            try:
                sync_youtube_channel(profile, user_id=user_id)
            except Exception as e:
                print(f"[Background Sync Error] {e}")

@settings_bp.route("/settings/sync-youtube/<int:profile_id>", methods=["POST"])
def sync_youtube(profile_id):
    """Manually trigger sync for a YouTube profile (backgrounded)."""
    if not g.user_id:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        return redirect(url_for("auth.login"))

    profile = SocialProfile.query.get_or_404(profile_id)
    if profile.user_id != g.user_id or profile.platform != "youtube":
        return redirect(url_for("settings.settings"))

    # Start the sync in the background
    thread = threading.Thread(
        target=run_sync_in_background,
        args=(current_app._get_current_object(), profile.id, g.user_id),
        daemon=True
    )
    thread.start()
    
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    msg = "Sync started! New videos will appear in your vault shortly."
    
    if is_ajax:
        return jsonify({"status": "success", "message": msg})
    
    flash(msg, "success")
    return redirect(url_for("settings.settings"))


def sync_youtube_channel(profile, user_id=None):
    """Fetch new videos from a YouTube channel RSS feed and import transcripts."""
    if not profile.channel_id:
        return 0, "No channel ID found. Try removing and re-adding the profile."

    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={profile.channel_id}"
    print(f"[Sync] Fetching RSS: {rss_url}")

    try:
        feed = feedparser.parse(rss_url)
    except Exception as e:
        return 0, f"Failed to fetch RSS feed: {e}"

    if not feed.entries:
        return 0, f"No videos found in RSS feed for channel {profile.channel_id}"

    print(f"[Sync] Found {len(feed.entries)} videos in RSS feed")

    imported = 0
    # Get existing content titles to avoid duplicates
    existing_titles = set(
        c.title for c in Content.query.filter_by(user_id=profile.user_id).all()
    )

    for entry in feed.entries[:5]:  # Check last 5 videos
        video_id = entry.get("yt_videoid", "")
        title = entry.get("title", "YouTube Video")
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        print(f"[Sync] Checking video: {title} ({video_id})")

        # Skip if already imported
        if title in existing_titles:
            print(f"[Sync] Skipping (already exists): {title}")
            continue

        try:
            transcript = get_youtube_transcript(video_url)
            if transcript:
                content = Content(
                    user_id=profile.user_id,
                    title=title,
                    body=transcript,
                    content_type="youtube",
                )
                db.session.add(content)
                db.session.commit() # Commit to get content.id

                # Generate embedding
                try:
                    embedding = get_embedding(content.body, user_id=user_id)
                    if embedding:
                        db.session.add(
                            Embedding(
                                content_id=content.id,
                                vector=json.dumps(embedding)
                            )
                        )
                        db.session.commit()
                except Exception as e:
                    print(f"[Sync] Embedding failed for {title}: {e}")

                imported += 1
                print(f"[Sync] Imported: {title}")
            else:
                print(f"[Sync] No transcript available for: {title}")
        except Exception as e:
            print(f"[Sync] Error importing {title}: {e}")
            continue

    if imported > 0:
        profile.last_synced_video = feed.entries[0].get("yt_videoid", "")
        db.session.commit()

    return imported, ""


# ─────────────────────────────────────────────────────────────
# API USAGE ENDPOINT (for frontend quota display)
# ─────────────────────────────────────────────────────────────

@settings_bp.route("/api/usage")
def api_usage():
    """Returns JSON with per-API-type usage stats for the current user."""
    if not g.user_id:
        return jsonify({"error": "Unauthorized"}), 401

    stats = get_usage_stats(g.user_id)
    return jsonify(stats)
