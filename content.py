import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
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


def allowed_file(filename):
    """Check if the file extension is allowed."""
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS


def extract_text(file):
    filename = file.filename.lower()
    if filename.endswith(".txt"):
        return file.read().decode("utf-8")

    if filename.endswith(".pdf"):
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text

    return ""

@content_bp.route("/add", methods=["GET", "POST"])
def add_content():
    if "user_id" not in session:
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
            body = extract_text(file)

        if not body:
            flash("No content provided. Please enter text, upload a file, or provide a YouTube URL.", "error")
            return redirect(url_for("content.add_content"))

        # 1️⃣ CREATE Content object
        content = Content(
            user_id=session["user_id"],
            title=title,
            body=body,
            content_type=content_type,
        )

        # 2️⃣ SAVE content FIRST
        db.session.add(content)
        db.session.commit()   # <-- content.id exists AFTER this line

        # 3️⃣ TRY embedding
        try:
            embedding = get_embedding(content.body)
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
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    content = Content.query.get_or_404(content_id)

    if content.user_id != session["user_id"]:
        return redirect(url_for("dashboard"))

    return render_template("view_content.html", content=content)
