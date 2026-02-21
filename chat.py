from flask import Blueprint, render_template, request, session, redirect, url_for
from models import Content
from dotenv import load_dotenv
import os
from groq import Groq

load_dotenv()

chat_bp = Blueprint("chat", __name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

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
            f"Title: {c.title}\n{c.body[:500]}" for c in contents
        )

        prompt = f"""You are the personal AI assistant for a content creator. You have access to their saved knowledge vault below.

YOUR ROLE:
- Study the creator's content carefully — understand their topics, writing style, tone, and perspective.
- Answer the user's question using insights and themes from their vault content.
- Match the creator's natural language and tone in your response.
- If the question relates to a topic covered in the vault, draw from that content to give a thoughtful answer.
- For general questions, you may use your general knowledge BUT frame the answer in a way that connects to the creator's interests and style.
- NEVER make up facts about what the creator said or wrote. If you're using general knowledge, be transparent.
- Keep answers concise and helpful.

CREATOR'S VAULT CONTENT:
{context}

USER'S QUESTION:
{question}

ANSWER (in the creator's tone and style):"""

        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024,
            )
            answer = response.choices[0].message.content
        except Exception as e:
            answer = f"Something went wrong: {e}"


    return render_template("chat.html", answer=answer)
