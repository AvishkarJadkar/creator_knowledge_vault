import os
import sys
from dotenv import load_dotenv
load_dotenv()

# --- Vercel serverless: ensure project root is in sys.path ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Flask, redirect, url_for, session, render_template, request
from extensions import db
from auth import auth_bp
from content import content_bp
from models import Content
from search import search_bp
from chat import chat_bp
from remix import remix_bp
from settings import settings_bp
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"), static_folder=os.path.join(BASE_DIR, "static"))

# --- SECURITY: Secret key (no hardcoded fallback in production) ---
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    if os.environ.get("FLASK_ENV") == "development":
        app.secret_key = "dev-secret-key-ONLY-for-local"
    else:
        raise RuntimeError(
            "SECRET_KEY environment variable is required for production! "
            "Set it in your Vercel project settings."
        )

# --- SECURITY: CSRF Protection ---
csrf = CSRFProtect(app)

# --- SECURITY: Rate Limiting ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# --- SECURITY: Secure session cookies ---
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
if os.environ.get("FLASK_ENV") != "development":
    app.config["SESSION_COOKIE_SECURE"] = True

# --- SECURITY: Max content length (16 MB) ---
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# --- DATABASE: PostgreSQL in production, SQLite for local dev ---
database_url = os.environ.get("DATABASE_URL", "sqlite:///vault.db")
# Render uses postgres:// but SQLAlchemy requires postgresql://
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

from models import User  # noqa

app.register_blueprint(auth_bp)
app.register_blueprint(content_bp)
app.register_blueprint(search_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(remix_bp)
app.register_blueprint(settings_bp)

# Create DB tables on first request (works with gunicorn)
with app.app_context():
    db.create_all()


# --- SECURITY: Force HTTPS in production ---
@app.before_request
def force_https():
    if os.environ.get("FLASK_ENV") != "development":
        if request.headers.get("X-Forwarded-Proto") == "http":
            url = request.url.replace("http://", "https://", 1)
            return redirect(url, code=301)


# --- SECURITY: Security headers ---
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    contents = Content.query.filter_by(
        user_id=session["user_id"]
    ).order_by(Content.created_at.desc()).all()

    return render_template("dashboard.html", contents=contents)

if __name__ == "__main__":
    os.environ.setdefault("FLASK_ENV", "development")
    app.run(host="0.0.0.0", port=8000, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
