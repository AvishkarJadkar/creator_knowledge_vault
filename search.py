from flask import Blueprint, render_template, request, redirect, url_for, g, jsonify
from extensions import db
from models import Content, Embedding
from ai import get_embedding, cosine_similarity
import json

search_bp = Blueprint("search", __name__)


def build_snippet(body, query, radius=80):
    """Return a short excerpt centred on the first match of `query`.

    Semantic results often don't contain the literal query, in which case we
    fall back to the beginning of the document.
    """
    body = body or ""
    query = query or ""

    if query:
        pos = body.lower().find(query.lower())
        if pos != -1:
            start = max(pos - radius, 0)
            end = min(pos + len(query) + radius, len(body))
            snippet = body[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(body):
                snippet += "..."
            return snippet

    return body[:200] + ("..." if len(body) > 200 else "")

@search_bp.route("/search", methods=["GET", "POST"])
def search():
    if not g.user_id:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Unauthorized"}), 401
        return redirect(url_for("auth.login"))

    results = []
    
    # Handle both GET for direct links and POST for form submissions
    query = request.form.get("query") if request.method == "POST" else request.args.get("q")
    query = (query or "").strip()

    # --- SECURITY: Limit query length ---
    if len(query) > 500:
        query = query[:500]

    if query:
        # 1. Try Semantic Search FIRST
        query_embedding = get_embedding(query, user_id=g.user_id)
        
        if query_embedding:
            # Join Content and Embedding in a single query
            # We filter by user_id and is_deleted at the database level
            data = db.session.query(Content, Embedding).join(
                Embedding, Content.id == Embedding.content_id
            ).filter(
                Content.user_id == g.user_id,
                Content.is_deleted == False
            ).all()

            if data:
                scored_results = []
                for content, emb in data:
                    try:
                        vector = json.loads(emb.vector)
                        score = cosine_similarity(query_embedding, vector)
                        if score > 0.15: # Slightly higher threshold for efficiency
                            scored_results.append((score, content))
                    except (json.JSONDecodeError, ValueError):
                        continue
                
                # Sort by score DESC and take top results
                scored_results.sort(key=lambda x: x[0], reverse=True)
                results = [item[1] for item in scored_results[:20]]

        # 2. Fallback to Keyword Search (if semantic search fails or returns nothing)
        if not results:
            # --- SECURITY: Escape SQL wildcard characters to prevent injection ---
            safe_query = query.replace("%", r"\%").replace("_", r"\_")
            results = Content.query.filter(
                Content.user_id == g.user_id,
                Content.is_deleted == False,
                Content.body.ilike(f"%{safe_query}%")
            ).all()

            # Also search by title if body search returned nothing
            if not results:
                results = Content.query.filter(
                    Content.user_id == g.user_id,
                    Content.is_deleted == False,
                    Content.title.ilike(f"%{safe_query}%")
                ).all()

    # --- Server-side render: attach snippets once, so the template and the
    # AJAX response show exactly the same excerpt (including semantic matches
    # that don't contain the literal query).
    for c in results:
        c.snippet = build_snippet(c.body, query)

    # --- AJAX Response ---
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "results": [{
                "id": c.id,
                "title": c.title,
                "body_snippet": c.snippet,
                "content_type": c.content_type,
                "created_at": c.created_at.strftime("%b %d, %Y") if c.created_at else ""
            } for c in results],
            "query": query
        })

    return render_template("search.html", results=results, query=query)
