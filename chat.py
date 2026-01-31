from flask import Blueprint, render_template, request, session, redirect, url_for
from models import Content
from dotenv import load_dotenv
import os
from google import genai

load_dotenv()

chat_bp = Blueprint("chat", __name__)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

@chat_bp.route("/chat", methods=["GET", "POST"])
def chat():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    answer = None

    if request.method == "POST":
        question = request.form["question"]

        contents = Content.query.filter_by(user_id=session["user_id"]).all()
        if not contents:
            answer = "Your vault is empty."
            return render_template("chat.html", answer=answer)
        
        contents = contents[:10]  # limit to last 10 items
        context = "\n\n".join(
            f"Title: {c.title}\n{c.body}" for c in contents
        )

        prompt = f"""
            You are an assistant answering ONLY using the user's content.

            STRICT RULES:
            - Do NOT use outside knowledge
            - Do NOT hallucinate
            - If unsure, say exactly: Not found in your vault.

            CONTENT:
            {context}

            QUESTION:
            {question}

            ANSWER:
            """

        try:
            response = client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=prompt,
        )

            answer = response.text
        except Exception as e:
            answer = "Something went wrong. Try again."


    return render_template("chat.html", answer=answer)
