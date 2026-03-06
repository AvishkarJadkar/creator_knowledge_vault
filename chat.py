from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from models import Content, Embedding, ChatSession, ChatMessage, Memory
from extensions import db
from dotenv import load_dotenv
import os
import json
import re
from datetime import datetime, timedelta
from groq import Groq
from ai import get_embedding, cosine_similarity

load_dotenv()

chat_bp = Blueprint("chat", __name__)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_chat_title(user_msg, bot_msg):
    """Uses LLM to generate a short, contextual chat title."""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": f"Generate a short chat title (3-5 words max, no quotes, no punctuation) that summarizes this conversation:\n\nUser: {user_msg}\nAssistant: {bot_msg[:200]}\n\nTitle:"}],
            temperature=0.7,
            max_tokens=15
        )
        title = response.choices[0].message.content.strip().strip('"\'')
        # Remove any trailing punctuation
        title = title.rstrip('.!?')
        return title[:50] if len(title) > 3 else "New Chat"
    except:
        return user_msg[:50]

def extract_fact(text, history):
    """Uses LLM to extract a clean fact from 'remember' style messages."""
    prompt = f"""Extract ONLY the explicitly stated fact from the user's message.
Format as a single, concise sentence starting with "The user...".
If the message is vague (e.g., "remember name" without giving a name), return "NONE".
DO NOT infer or guess details. If no clear fact is stated, return "NONE".

CONTEXT:
{history}

USER MESSAGE:
{text}

EXTRACTED FACT:"""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=100
        )
        fact = response.choices[0].message.content.strip()
        # Clean up common AI prefixes if any
        fact = re.sub(r'^(Here is the fact:|Fact:|Extracted Fact:)\s*', '', fact, flags=re.IGNORECASE).strip()
        return None if "NONE" in fact.upper() or len(fact) < 5 else fact
    except:
        return None

@chat_bp.route("/chat")
@chat_bp.route("/chat/<int:session_id>")
def chat(session_id=None):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_sessions = ChatSession.query.filter_by(user_id=session["user_id"]).order_by(ChatSession.updated_at.desc()).all()
    user_memories = Memory.query.filter_by(user_id=session["user_id"]).order_by(Memory.created_at.desc()).all()
    
    active_session = None
    messages = []
    
    if session_id:
        active_session = ChatSession.query.get_or_404(session_id)
        if active_session.user_id != session["user_id"]:
            return redirect(url_for("chat.chat"))
        messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.created_at.asc()).all()
    
    # Group sessions by date
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    
    grouped_sessions = {
        "today": [],
        "previous_7_days": [],
        "older": []
    }
    
    for s in user_sessions:
        s_date = s.updated_at.date()
        if s_date == today:
            grouped_sessions["today"].append(s)
        elif s_date >= week_ago:
            grouped_sessions["previous_7_days"].append(s)
        else:
            grouped_sessions["older"].append(s)
    
    return render_template("chat.html", 
                           sessions=user_sessions, 
                           grouped_sessions=grouped_sessions,
                           active_session=active_session,
                           messages=messages,
                           memories=user_memories)

@chat_bp.route("/chat/new", methods=["POST"])
def new_chat():
    if "user_id" not in session:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "Not logged in"}), 401
        return redirect(url_for("auth.login"))
    
    new_sess = ChatSession(user_id=session["user_id"], title="New Chat")
    db.session.add(new_sess)
    db.session.commit()
    
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"session_id": new_sess.id, "url": url_for("chat.chat", session_id=new_sess.id)})
    return redirect(url_for("chat.chat", session_id=new_sess.id))


@chat_bp.route("/chat/<int:session_id>/send", methods=["POST"])
def send_message(session_id):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
        
    chat_sess = ChatSession.query.get_or_404(session_id)
    if chat_sess.user_id != session["user_id"]:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Accept both form data and JSON
    if request.is_json:
        question = request.json.get("question", "").strip()
    else:
        question = request.form.get("question", "").strip()
    
    if not question:
        return jsonify({"error": "Empty message"}), 400

    # --- SECURITY: Limit message length to prevent abuse ---
    if len(question) > 10000:
        return jsonify({"error": "Message too long. Maximum 10,000 characters."}), 400

    # 1. Save User Message
    user_msg = ChatMessage(session_id=session_id, role="user", content=question)
    db.session.add(user_msg)
    
    # Title will be generated after AI responds (see below)
    is_first_message = chat_sess.title == "New Chat"
    
    db.session.commit()

    # 2. Check for Memory Trigger
    memory_saved_fact = None
    # Broaden detection for natural statements like "my name is..." or "I live in..."
    if re.search(r'\bremember\b|\bsave (this|that)\b|\bdon.?t forget\b|\bmy (name|job|location|role|favorite) is\b|\bi am a\b', question.lower()):
        # Fetch last few messages for context
        history = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.created_at.desc()).limit(5).all()
        history_text = "\n".join([f"{m.role}: {m.content}" for m in reversed(history)])
        
        extracted = extract_fact(question, history_text)
        if extracted:
            new_mem = Memory(user_id=session["user_id"], fact=extracted)
            db.session.add(new_mem)
            db.session.commit()
            memory_saved_fact = extracted

    # 3. RAG Retrieval
    context_parts = []
    try:
        query_embedding = get_embedding(question)
        if query_embedding:
            # Get user content
            all_contents = Content.query.filter_by(user_id=session["user_id"]).all()
            content_ids = [c.id for c in all_contents]
            content_map = {c.id: c for c in all_contents}
            
            # Fetch embeddings
            embeddings = Embedding.query.filter(Embedding.content_id.in_(content_ids)).all()
            
            scored_results = []
            for emb in embeddings:
                vector = json.loads(emb.vector)
                score = cosine_similarity(query_embedding, vector)
                if score > 0.3:
                    scored_results.append((score, content_map[emb.content_id]))
            
            scored_results.sort(key=lambda x: x[0], reverse=True)
            top_results = scored_results[:5] # Top 5 relevant snippets
            
            for _, c in top_results:
                context_parts.append(f"Title: {c.title}\n{c.body[:1000]}") # Longer snippets for better context
            
    except Exception as e:
        print(f"Retrieval error: {e}")

    # Fallback context if RAG fails or returns nothing
    if not context_parts:
        contents = Content.query.filter_by(user_id=session["user_id"]).order_by(Content.created_at.desc()).limit(5).all()
        context_parts = [f"Title: {c.title}\n{c.body[:500]}" for c in contents]

    context = "\n\n".join(context_parts)

    # 4. Load Memories
    user_memories = Memory.query.filter_by(user_id=session["user_id"]).all()
    memories_str = "\n".join([f"- {m.fact}" for m in user_memories]) if user_memories else "No specific personal facts saved yet."

    # 5. Build Multi-Turn History
    # Get last 6 messages for context
    history_msgs = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.created_at.desc()).limit(7).all()
    history_msgs.reverse() # Sort back to chronological
    
    system_prompt = f"""You are a friendly, conversational AI assistant for a content creator's knowledge vault. Talk like a helpful friend — casual, warm, and concise.

## TONE & LENGTH:
- For casual messages (greetings, small talk) → reply in 1-2 short sentences. NO headings, NO bullet points. Just be natural.
- For detailed questions (lists, comparisons, explanations) → use Markdown formatting: **bold**, bullet points, headings.
- Match the energy of the user's message. Short question = short answer.

## PERSONAL QUESTIONS (name, age, location, job, etc.):
- ONLY answer from SAVED MEMORIES below.
- If not in memories → say "I don't have that saved yet! Tell me and I'll remember it 😊"
- NEVER guess or invent personal details. NEVER pull personal info from vault content.

## RULES:
- NEVER fabricate information. If unsure, say so.
- If you saved a memory this turn (see system note), briefly confirm it.

## SAVED MEMORIES:
{memories_str}

## VAULT CONTENT (user's own created content — NOT personal info about them):
{context}

## CONTENT QUESTIONS:
- "What have I covered?" → list titles from vault content above.
- "Suggest topics" → suggest NEW topics not already in the list.
"""

    llm_messages = [{"role": "system", "content": system_prompt}]
    for m in history_msgs:
        llm_messages.append({"role": m.role, "content": m.content})
    
    # If a memory was just saved, tell the AI so it can confirm
    if memory_saved_fact:
        llm_messages.append({"role": "system", "content": f"[SYSTEM NOTE: You just saved this fact to your long-term memory: '{memory_saved_fact}'. Confirm this to the user in your response.]"})

    # 6. Call LLM
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=llm_messages,
            temperature=0,
            max_tokens=1024,
        )
        answer = response.choices[0].message.content
        
        # Save Assistant Message
        bot_msg = ChatMessage(session_id=session_id, role="assistant", content=answer)
        db.session.add(bot_msg)
        
        # Generate smart title after first exchange
        new_title = None
        if is_first_message:
            chat_sess.title = generate_chat_title(question, answer)
            new_title = chat_sess.title
        db.session.commit()
        
        from datetime import datetime
        now = datetime.utcnow()
        
        return jsonify({
            "answer": answer,
            "time": now.strftime('%H:%M'),
            "new_title": new_title,
            "memory_saved": memory_saved_fact
        })
    except Exception as e:
        # --- SECURITY: Don't expose internal errors to users ---
        print(f"Chat error: {e}")
        return jsonify({"error": "Something went wrong. Please try again."}), 500


@chat_bp.route("/chat/<int:session_id>/delete", methods=["POST"])
def delete_session(session_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
        
    chat_sess = ChatSession.query.get_or_404(session_id)
    if chat_sess.user_id != session["user_id"]:
        return redirect(url_for("chat.chat"))
        
    db.session.delete(chat_sess)
    db.session.commit()
    flash("Conversation deleted", "success")
    return redirect(url_for("chat.chat"))

@chat_bp.route("/chat/memory/<int:memory_id>/delete", methods=["POST"])
def delete_memory(memory_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    
    mem = Memory.query.get_or_404(memory_id)
    if mem.user_id != session["user_id"]:
        return redirect(url_for("chat.chat"))
        
    db.session.delete(mem)
    db.session.commit()
    flash("Memory removed", "success")
    return redirect(url_for("chat.chat"))
