from flask import Blueprint, render_template, request, session, redirect, url_for
from models import Content
from dotenv import load_dotenv
import os
from google import genai

load_dotenv()

remix_bp = Blueprint("remix", __name__)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

PROMPTS = {
    "twitter": "Turn the following content into a concise Twitter/X thread. Use numbered tweets.",
    "linkedin": "Turn the following content into a professional LinkedIn post. Clear, insightful, no emojis.",
    "summary": "Summarize the following content in clear bullet points.",
    "ideas": "Generate 5 new content ideas inspired by the following content."
}

@remix_bp.route("/remix/<int:content_id>", methods=["GET", "POST"])
def remix(content_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    content = Content.query.get_or_404(content_id)

    output = None

    if request.method == "POST":
        remix_type = request.form["remix_type"]

        prompt = f"""
{PROMPTS[remix_type]}

CONTENT:
{content.body}

OUTPUT:
"""

        try:
            response = client.models.generate_content(
                model="models/gemini-2.5-flash",
                contents=prompt,
            )
            output = response.text
        except Exception as e:
            output = f"Remix error: {e}"

    return render_template("remix.html", content=content, output=output)
