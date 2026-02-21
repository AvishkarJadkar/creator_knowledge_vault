import re
import feedparser
import urllib.request
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from extensions import db
from models import SocialProfile, Content
from youtube_utils import get_youtube_transcript

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
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    profiles = SocialProfile.query.filter_by(user_id=session["user_id"]).all()
    return render_template("settings.html", profiles=profiles)


@settings_bp.route("/settings/add-profile", methods=["POST"])
def add_profile():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    platform = request.form["platform"]
    profile_url = request.form["profile_url"].strip()

    if not profile_url:
        flash("Please enter a profile URL", "error")
        return redirect(url_for("settings.settings"))

    # Check for duplicate
    existing = SocialProfile.query.filter_by(
        user_id=session["user_id"],
        platform=platform,
        profile_url=profile_url
    ).first()
    if existing:
        flash("This profile is already linked", "error")
        return redirect(url_for("settings.settings"))

    channel_id = None
    if platform == "youtube":
        channel_id = resolve_channel_id(profile_url)
        if not channel_id:
            flash("Could not detect YouTube channel. Make sure the URL is correct.", "error")
            return redirect(url_for("settings.settings"))

    profile = SocialProfile(
        user_id=session["user_id"],
        platform=platform,
        profile_url=profile_url,
        channel_id=channel_id,
    )
    db.session.add(profile)
    db.session.commit()

    flash(f"{platform.title()} profile linked successfully!", "success")
    return redirect(url_for("settings.settings"))


@settings_bp.route("/settings/remove-profile/<int:profile_id>", methods=["POST"])
def remove_profile(profile_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    profile = SocialProfile.query.get_or_404(profile_id)
    if profile.user_id != session["user_id"]:
        return redirect(url_for("settings.settings"))

    db.session.delete(profile)
    db.session.commit()
    flash("Profile removed", "success")
    return redirect(url_for("settings.settings"))


@settings_bp.route("/settings/sync-youtube/<int:profile_id>", methods=["POST"])
def sync_youtube(profile_id):
    """Manually trigger sync for a YouTube profile."""
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    profile = SocialProfile.query.get_or_404(profile_id)
    if profile.user_id != session["user_id"] or profile.platform != "youtube":
        return redirect(url_for("settings.settings"))

    imported, errors = sync_youtube_channel(profile)
    if imported > 0:
        flash(f"Imported {imported} new video(s) from YouTube!", "success")
    elif errors:
        flash(f"Sync issue: {errors}", "error")
    else:
        flash("No new videos found to import.", "")
    return redirect(url_for("settings.settings"))


def sync_youtube_channel(profile):
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
