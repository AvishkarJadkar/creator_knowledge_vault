import os
from flask import Blueprint, render_template, request, redirect, url_for, session
from extensions import db
from models import Content
from pypdf import PdfReader
import json
from ai import get_embedding
from models import Embedding
from youtube_utils import get_youtube_transcript
from youtube_utils import get_youtube_transcript, get_youtube_title


content_bp = Blueprint("content", __name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def extract_text(file):
    if file.filename.endswith(".txt"):
        return file.read().decode("utf-8")

    if file.filename.endswith(".pdf"):
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
        title = request.form["title"]
        content_type = request.form["content_type"]
        body = request.form.get("body", "")

        youtube_url = request.form.get("youtube_url")

        if youtube_url:
            try:
                body = get_youtube_transcript(youtube_url)
                title = get_youtube_title(youtube_url)
                content_type = "youtube"

            except Exception as e:
                return f"Failed to fetch YouTube transcript: {e}"

        file = request.files.get("file")
        if file and file.filename:
            body = extract_text(file)

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

        # 3️⃣ TRY embedding (OPTION A)
        try:
            embedding = get_embedding(content.body)
            db.session.add(
                Embedding(
                    content_id=content.id,
                    vector=json.dumps(embedding)
                )
            )
            db.session.commit()
        except Exception as e:
            print("Embedding skipped:", e)

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
