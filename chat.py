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

        context = "\n\n".join(
            f"Title: {c.title}\n{c.body}" for c in contents
        )

        prompt = f"""
            You are an assistant helping a creator answer questions using their own notes.

            RULES:
            - Use ONLY the content provided below
            - Do NOT repeat the content verbatim
            - Do NOT list titles unless asked
            - Answer in clear natural language
            - If the answer is not found, say exactly: Not found in your vault.

            CONTENT START
            {context}
            CONTENT END

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
            answer = f"Chat error: {e}"

    return render_template("chat.html", answer=answer)
