from flask import Blueprint, render_template, request, session, redirect, url_for
from models import Content

search_bp = Blueprint("search", __name__)

@search_bp.route("/search", methods=["GET", "POST"])
def search():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    results = []

    if request.method == "POST":
        query = request.form["query"]

        results = Content.query.filter(
            Content.user_id == session["user_id"],
            Content.body.ilike(f"%{query}%")
        ).all()

    return render_template("search.html", results=results)
