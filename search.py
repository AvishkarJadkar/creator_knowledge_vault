from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from models import Content, Embedding
from ai import get_embedding, cosine_similarity
import json

search_bp = Blueprint("search", __name__)

@search_bp.route("/search", methods=["GET", "POST"])
def search():
    if "user_id" not in session:
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
        query_embedding = get_embedding(query)
        
        if query_embedding:
            # Get all embeddings for this user
            all_contents = Content.query.filter_by(user_id=session["user_id"], is_deleted=False).all()
            content_ids = [c.id for c in all_contents]
            
            embeddings = Embedding.query.filter(Embedding.content_id.in_(content_ids)).all()
            
            if embeddings:
                # Calculate similarities
                scored_results = []
                # Map content ID to content object for easy access
                content_map = {c.id: c for c in all_contents}
                
                for emb in embeddings:
                    vector = json.loads(emb.vector)
                    score = cosine_similarity(query_embedding, vector)
                    if score > 0.1: # Threshold to filter out irrelevant stuff
                        scored_results.append((score, content_map[emb.content_id]))
                
                # Sort by score DESC
                scored_results.sort(key=lambda x: x[0], reverse=True)
                results = [item[1] for item in scored_results]

        # 2. Fallback to Keyword Search (if semantic search fails or returns nothing)
        if not results:
            # --- SECURITY: Escape SQL wildcard characters to prevent injection ---
            safe_query = query.replace("%", r"\%").replace("_", r"\_")
            results = Content.query.filter(
                Content.user_id == session["user_id"],
                Content.is_deleted == False,
                Content.body.ilike(f"%{safe_query}%")
            ).all()

            # Also search by title if body search returned nothing
            if not results:
                results = Content.query.filter(
                    Content.user_id == session["user_id"],
                    Content.is_deleted == False,
                    Content.title.ilike(f"%{safe_query}%")
                ).all()

    # --- AJAX Response ---
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "results": [{
                "id": c.id,
                "title": c.title,
                "body_snippet": c.body[:200] + "..." if len(c.body) > 200 else c.body,
                "content_type": c.content_type,
                "created_at": c.created_at.strftime("%b %d, %Y")
            } for c in results],
            "query": query
        })

    return render_template("search.html", results=results, query=query)
