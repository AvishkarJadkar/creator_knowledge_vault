from flask import Blueprint, render_template, request, session, redirect, url_for
from models import Content, Embedding
from ai import get_embedding, cosine_similarity
import json

search_bp = Blueprint("search", __name__)

@search_bp.route("/search", methods=["GET", "POST"])
def search():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    results = []
    query = request.form.get("query", "").strip()

    # --- SECURITY: Limit query length ---
    if len(query) > 500:
        query = query[:500]

    if request.method == "POST" and query:
        # 1. Try Semantic Search FIRST
        query_embedding = get_embedding(query)
        
        if query_embedding:
            # Get all embeddings for this user
            all_contents = Content.query.filter_by(user_id=session["user_id"]).all()
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
                
                # If we found semantic results, we can return them
                if results:
                    return render_template("search.html", results=results, query=query)

        # 2. Fallback to Keyword Search (if semantic search fails or returns nothing)
        # --- SECURITY: Escape SQL wildcard characters to prevent injection ---
        safe_query = query.replace("%", r"\%").replace("_", r"\_")
        results = Content.query.filter(
            Content.user_id == session["user_id"],
            Content.body.ilike(f"%{safe_query}%", escape="\\")
        ).all()

    return render_template("search.html", results=results, query=query)
