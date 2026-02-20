from flask import Blueprint, render_template, request, session, redirect, url_for
from models import Content
from dotenv import load_dotenv
import os
from groq import Groq

load_dotenv()

remix_bp = Blueprint("remix", __name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

PROMPTS = {
    "twitter": """You are a top-tier social media ghostwriter. Turn the content below into a viral Twitter/X thread.

RULES:
- Start with a powerful hook tweet that grabs attention (use a bold statement, surprising stat, or provocative question)
- Number each tweet (1/, 2/, etc.)
- Keep each tweet under 280 characters
- Use short punchy sentences. One idea per tweet.
- Add line breaks within tweets for readability
- End with a strong call-to-action tweet
- 5-8 tweets total, no fluff
- No hashtags unless absolutely necessary
- Write like a creator who knows their stuff, not a corporate account""",

    "linkedin": """You are a LinkedIn content strategist who writes posts that get massive engagement. Transform the content below into a high-performing LinkedIn post.

RULES:
- Open with a bold first line that stops the scroll (one sentence, followed by a line break)
- Use short paragraphs (1-2 sentences each)
- Add line breaks between every paragraph for readability
- Include a personal insight or contrarian take
- Use "→" arrows for key takeaways
- End with a thought-provoking question to drive comments
- Tone: confident, insightful, conversational — NOT corporate or generic
- No emojis, no hashtags
- Total length: 150-250 words""",

    "summary": """You are an expert at distilling complex content into clear, scannable summaries. Summarize the content below.

RULES:
- Start with a one-sentence TL;DR in bold
- Follow with 4-6 bullet points covering the key insights
- Each bullet should be a complete, standalone insight (not just a topic mention)
- Use "→" before each bullet
- End with a "Bottom line:" one-liner
- Be specific — include numbers, names, and concrete details from the content
- Cut all filler words and vague statements
- Write so someone can understand the content in 30 seconds""",

    "ideas": """You are a creative strategist who helps content creators generate their next viral piece. Based on the content below, generate fresh content ideas.

RULES:
- Generate exactly 5 content ideas
- Number them 1-5
- Each idea should have:
  • A catchy title/headline (bold it)
  • A 1-2 sentence description of the angle or hook
  • The format suggestion (thread, video, carousel, newsletter, etc.)
- Ideas should be DIFFERENT angles, not repetitions of the original
- Mix formats: at least one contrarian take, one how-to, and one story-driven idea
- Make titles specific and curiosity-driven, not generic"""
}

@remix_bp.route("/remix/<int:content_id>", methods=["GET", "POST"])
def remix(content_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    content = Content.query.get_or_404(content_id)

    output = None

    if request.method == "POST":
        remix_type = request.form["remix_type"]

        prompt = f"""{PROMPTS[remix_type]}

CONTENT TO REMIX:
{content.body[:2000]}

YOUR OUTPUT (ready to copy-paste, no meta-commentary):"""

        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are a world-class content creator. Your output is always polished, engaging, and ready to publish. Never add disclaimers, explanations, or meta-commentary. Just deliver the content."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=1500,
            )
            output = response.choices[0].message.content
        except Exception as e:
            output = f"Remix error: {e}"

    return render_template("remix.html", content=content, output=output)
