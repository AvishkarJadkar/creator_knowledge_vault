import os
from flask import Blueprint, render_template, request, redirect, url_for, session
from extensions import db
from models import Content
from pypdf import PdfReader

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

        file = request.files.get("file")
        if file and file.filename:
            body = extract_text(file)

        content = Content(
            user_id=session["user_id"],
            title=title,
            body=body,
            content_type=content_type,
        )

        db.session.add(content)
        db.session.commit()

        return redirect(url_for("dashboard"))

    return render_template("add_content.html")
