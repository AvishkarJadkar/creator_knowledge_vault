from flask import Blueprint, render_template, request, session, redirect, url_for
from .providers import PROVIDERS
from ai import generate_summary

explore_bp = Blueprint("explore", __name__)

@explore_bp.route("/explore")
def explore():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    
    return render_template("explore.html", providers=PROVIDERS.values(), results=None, summary=None)

@explore_bp.route("/explore/search")
def search():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    keyword = request.args.get("q", "").strip()
    provider_name = request.args.get("provider", "reddit")
    
    if not keyword:
        return redirect(url_for("explore.explore"))

    provider = PROVIDERS.get(provider_name)
    if not provider:
        provider = PROVIDERS.get("reddit")

    # 1. Fetch search results
    results = provider.search(keyword, limit=5)
    
    # 2. Synthesize with AI
    if results:
        combined_content = f"Topic: {keyword}\n\n"
        for r in results:
            combined_content += r["raw_text"] + "\n\n---\n\n"
        
        summary = generate_summary(combined_content)
    else:
        summary = "No results found to summarize."

    return render_template(
        "explore.html", 
        providers=PROVIDERS.values(), 
        results=results, 
        summary=summary,
        keyword=keyword,
        active_provider=provider_name
    )
