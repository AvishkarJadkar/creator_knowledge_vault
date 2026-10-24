from flask import Blueprint, render_template, request, redirect, url_for, jsonify, g
from .providers import PROVIDERS
from ai import generate_summary

explore_bp = Blueprint("explore", __name__)


def _default_provider():
    return PROVIDERS.get("reddit") or next(iter(PROVIDERS.values()))


@explore_bp.route("/explore")
def explore():
    if not g.user_id:
        return redirect(url_for("auth.login"))

    provider = _default_provider()
    return render_template(
        "explore.html",
        providers=PROVIDERS.values(),
        results=None,
        summary=None,
        active_provider=provider.name,
        active_provider_name=provider.display_name,
        notice=None,
    )


@explore_bp.route("/explore/search")
def search():
    if not g.user_id:
        return redirect(url_for("auth.login"))

    keyword = request.args.get("q", "").strip()
    provider_name = request.args.get("provider", "reddit")

    if not keyword:
        return redirect(url_for("explore.explore"))

    provider = PROVIDERS.get(provider_name) or _default_provider()

    # 1. Fetch search results from the requested provider
    results = provider.search(keyword, limit=5)
    used_provider = provider
    notice = None

    # 2. Fall back to another registered provider (Reddit blocks most
    #    unauthenticated server requests with HTTP 403).
    if not results:
        fallback = PROVIDERS.get("hackernews")
        if fallback and fallback.name != provider.name:
            results = fallback.search(keyword, limit=5)
            if results:
                used_provider = fallback
                notice = (
                    f"{provider.display_name} returned no results for this search, "
                    f"so these come from {fallback.display_name} instead."
                )

    if not results:
        notice = (
            f"Could not fetch results from {provider.display_name}. "
            "Please try again in a moment or use a different keyword."
        )

    # 3. Synthesize with AI
    if results:
        combined_content = f"Topic: {keyword}\n\n"
        for r in results:
            combined_content += r["raw_text"] + "\n\n---\n\n"

        summary = generate_summary(combined_content, user_id=g.user_id)
    else:
        summary = None

    # --- AJAX Response ---
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "results": results,
            "summary": summary,
            "keyword": keyword,
            "provider": used_provider.name,
            "provider_name": used_provider.display_name,
            "notice": notice,
        })

    return render_template(
        "explore.html",
        providers=PROVIDERS.values(),
        results=results,
        summary=summary,
        keyword=keyword,
        active_provider=used_provider.name,
        active_provider_name=used_provider.display_name,
        notice=notice,
    )
