import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g, current_app
from extensions import db
from models import Content
from pypdf import PdfReader
import json
from ai import get_embedding
from models import Embedding
from youtube_utils import get_youtube_transcript, get_youtube_title


content_bp = Blueprint("content", __name__)

UPLOAD_FOLDER = os.path.join("/tmp", "uploads") if os.environ.get("VERCEL") else "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- SECURITY: Allowed file extensions ---
ALLOWED_EXTENSIONS = {".txt", ".pdf"}

# Content types the UI can create. "youtube" is assigned server-side.
ALLOWED_CONTENT_TYPES = {"note", "idea", "pdf", "youtube"}


def allowed_file(filename):
    """Check if the file extension is allowed."""
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS


def extract_text(file):
    filename = (file.filename or "").lower()
    if filename.endswith(".txt"):
        raw = file.read()
        # Try the common encodings before falling back to a lossless one.
        for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    if filename.endswith(".pdf"):
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text

    return ""

@content_bp.route("/add", methods=["GET", "POST"])
def add_content():
    if not g.user_id:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content_type = request.form.get("content_type", "").strip()
        body = request.form.get("body", "").strip()

        # --- SECURITY: Input validation ---
        if not title or len(title) > 200:
            flash("Title is required and must be under 200 characters", "error")
            return redirect(url_for("content.add_content"))

        if not content_type or len(content_type) > 50:
            flash("Content type is required", "error")
            return redirect(url_for("content.add_content"))

        # Only allow the types the UI actually offers (plus YouTube, which is
        # set server-side below). Anything else would render an unstyled badge
        # and pollute the vault with arbitrary strings.
        if content_type not in ALLOWED_CONTENT_TYPES:
            flash("Please choose a valid content type", "error")
            return redirect(url_for("content.add_content"))

        # --- SECURITY: Limit body size (500KB of text) ---
        if len(body) > 500_000:
            flash("Content is too large. Maximum 500KB of text allowed.", "error")
            return redirect(url_for("content.add_content"))

        youtube_url = request.form.get("youtube_url", "").strip()

        if youtube_url:
            # --- SECURITY: Basic URL validation ---
            if not youtube_url.startswith(("https://www.youtube.com/", "https://youtu.be/", "https://youtube.com/")):
                flash("Please enter a valid YouTube URL", "error")
                return redirect(url_for("content.add_content"))
            try:
                body = get_youtube_transcript(youtube_url)
                title = get_youtube_title(youtube_url)
                content_type = "youtube"
            except Exception:
                # --- SECURITY: Don't expose internal error details ---
                flash("Failed to fetch YouTube transcript. Please check the URL and try again.", "error")
                return redirect(url_for("content.add_content"))

        file = request.files.get("file")
        if file and file.filename:
            # --- SECURITY: Validate file extension ---
            if not allowed_file(file.filename):
                flash("Only .txt and .pdf files are allowed", "error")
                return redirect(url_for("content.add_content"))
            try:
                body = extract_text(file)
            except Exception as e:
                # Corrupt PDFs, encrypted files, etc. must not 500.
                current_app.logger.warning("File extraction failed: %s", e)
                flash("Could not read that file. Please upload a valid .txt or .pdf.", "error")
                return redirect(url_for("content.add_content"))

        if not body:
            flash("No content provided. Please enter text, upload a file, or provide a YouTube URL.", "error")
            return redirect(url_for("content.add_content"))

        # 1️⃣ CREATE Content object
        content = Content(
            user_id=g.user_id,
            title=title,
            body=body,
            content_type=content_type,
        )

        # 2️⃣ SAVE content FIRST
        db.session.add(content)
        db.session.commit()   # <-- content.id exists AFTER this line

        # 3️⃣ TRY embedding
        try:
            embedding = get_embedding(body, user_id=g.user_id)
            if embedding:
                db.session.add(
                    Embedding(
                        content_id=content.id,
                        vector=json.dumps(embedding)
                    )
                )
                db.session.commit()
        except Exception as e:
            print("Embedding failed:", e)

        # 4️⃣ Redirect regardless of embedding success
        return redirect(url_for("dashboard"))

    return render_template("add_content.html")

@content_bp.route("/content/<int:content_id>")
def view_content(content_id):
    if not g.user_id:
        return redirect(url_for("auth.login"))

    content = Content.query.filter_by(id=content_id, is_deleted=False).first_or_404()

    if content.user_id != g.user_id:
        return redirect(url_for("dashboard"))

    return render_template("view_content.html", content=content)

@content_bp.route("/content/<int:content_id>/delete", methods=["POST"])
def delete_content(content_id):
    if not g.user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    content = Content.query.filter_by(id=content_id, user_id=g.user_id).first_or_404()
    content.is_deleted = True
    db.session.commit()
    return jsonify({"success": True})

@content_bp.route("/content/<int:content_id>/restore", methods=["POST"])
def restore_content(content_id):
    if not g.user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    content = Content.query.filter_by(id=content_id, user_id=g.user_id).first_or_404()
    content.is_deleted = False
    db.session.commit()
    return jsonify({"success": True})

@content_bp.route("/content/delete_all", methods=["POST"])
def delete_all():
    if not g.user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    Content.query.filter_by(user_id=g.user_id).update({"is_deleted": True})
    db.session.commit()
    return jsonify({"success": True})

@content_bp.route("/content/restore_all", methods=["POST"])
def restore_all():
    if not g.user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    data = request.get_json(silent=True) or {}
    content_ids = data.get("content_ids")
    if not isinstance(content_ids, list) or not content_ids:
        return jsonify({"success": False, "error": "Invalid request"}), 400

    try:
        content_ids = [int(cid) for cid in content_ids]
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid request"}), 400

    Content.query.filter(
        Content.id.in_(content_ids),
        Content.user_id == g.user_id
    ).update({"is_deleted": False}, synchronize_session=False)
    db.session.commit()
    return jsonify({"success": True})
