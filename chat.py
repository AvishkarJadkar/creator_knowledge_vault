from flask import Blueprint, render_template, request, session, redirect, url_for
from models import Content
import google.generativeai as genai
import os

chat_bp = Blueprint("chat", __name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

@chat_bp.route("/chat", methods=["GET", "POST"])
def chat():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    answer = None

    if request.method == "POST":
        question = request.form["question"]

        contents = Content.query.filter_by(user_id=session["user_id"]).all()
        context = "\n\n".join(
            f"Title: {c.title}\n{c.body}" for c in contents
        )

        prompt = f"""
You are an assistant that can ONLY answer using the user's content below.
If the answer is not present, say: "Not found in your vault."

USER CONTENT:
{context}

QUESTION:
{question}
"""

        response = model.generate_content(prompt)
        answer = response.text

    return render_template("chat.html", answer=answer)
