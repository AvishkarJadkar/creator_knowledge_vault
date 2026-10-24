import os
import sys
import threading
from dotenv import load_dotenv
load_dotenv()

# --- Vercel serverless: ensure project root is in sys.path ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Flask, redirect, url_for, session, render_template, request, g, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from extensions import db
from auth import auth_bp
from content import content_bp
from search import search_bp
from chat import chat_bp
from remix import remix_bp
from settings import settings_bp
from explore import explore_bp
from flask_wtf.csrf import CSRFProtect, CSRFError

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"), static_folder=os.path.join(BASE_DIR, "static"))

# --- PROXY: trust the single reverse proxy in front of the app ---
# Render/Railway terminate TLS and forward X-Forwarded-* headers.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# --- SECURITY: Secret key ---
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    if os.environ.get("FLASK_ENV") == "development":
        app.secret_key = "dev-secret-key-ONLY-for-local"
    else:
        raise RuntimeError("SECRET_KEY required for production!")

# --- SECURITY: CSRF Protection ---
csrf = CSRFProtect(app)

# --- SECURITY: Secure session cookies ---
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
if os.environ.get("FLASK_ENV") != "development":
    app.config["SESSION_COOKIE_SECURE"] = True

# --- SECURITY: Max content length (16 MB) ---
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# --- DATABASE: PostgreSQL in production, SQLite for local dev ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Serverless platforms (Vercel) have a read-only filesystem except /tmp.
if os.environ.get("VERCEL"):
    INSTANCE_DIR = os.path.join("/tmp", "instance")
else:
    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)  # Ensure the instance directory exists

database_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(INSTANCE_DIR, 'vault.db')}")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
# SQLAlchemy 2.1 defaults `postgresql://` to the psycopg 3 driver, but this app
# ships psycopg2-binary. Pin the driver so any host-provided URL works as-is.
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(content_bp)
app.register_blueprint(search_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(remix_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(explore_bp)

from models import Content # Ensure models are loaded


def ensure_schema_upgrades():
    """Apply small schema upgrades that db.create_all() cannot handle.

    create_all() only creates missing *tables*; it never adds columns to an
    existing table. This keeps already-deployed databases working without
    pulling in a full migration framework.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "user_api_minute_usage" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("user_api_minute_usage")}
    if "api_type" not in columns:
        try:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE user_api_minute_usage ADD COLUMN api_type VARCHAR(50)"))
                # Old rows lumped every feature into one bucket; drop them.
                conn.execute(text("DELETE FROM user_api_minute_usage"))
        except Exception:
            # Another worker may have added the column between the check and
            # the ALTER; that's fine.
            app.logger.warning("Could not add api_type column (may already exist)", exc_info=True)

    index_names = {idx["name"] for idx in inspector.get_indexes("user_api_minute_usage")}
    if "ix_user_api_minute_usage_composite" not in index_names:
        try:
            with db.engine.begin() as conn:
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_user_api_minute_usage_composite "
                    "ON user_api_minute_usage (user_id, api_type)"
                ))
        except Exception:
            app.logger.warning("Could not create composite usage index", exc_info=True)


# --- DATABASE: create tables lazily on the first request ---------------------
# create_all() used to run at import time. That meant every serverless cold
# start paid for the round trips, and a database outage crashed the whole
# module (taking /health down with it). It now runs once per process, lazily.
_schema_ready = False
_schema_lock = threading.Lock()


def init_db_schema():
    """Create missing tables and apply small upgrades exactly once."""
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        db.create_all()
        ensure_schema_upgrades()
        _schema_ready = True


@app.before_request
def ensure_db_schema():
    if _schema_ready:
        return None
    try:
        init_db_schema()
    except Exception:
        # Leave _schema_ready False so the next request retries; individual
        # routes will surface their own errors if the DB is still unavailable.
        app.logger.exception("Database initialisation failed")
    return None

# --- AUTH MIDDLEWARE: Validate Firebase Session ---
@app.before_request
def load_user():
    g.user_id = session.get("user_id")
    g.user_name = session.get("user_name", "Creator")

# --- SECURITY: Force HTTPS in production ---
@app.before_request
def force_https():
    # Never redirect the platform health check: it arrives over the internal
    # network and some checkers don't follow redirects.
    if request.path == "/health":
        return None
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


# --- ERROR HANDLERS: friendly pages, JSON for AJAX ---
def _wants_json():
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes.best == "application/json"
    )


@app.errorhandler(404)
def not_found(error):
    if _wants_json():
        return jsonify({"error": "Not found"}), 404
    return render_template(
        "error.html", code=404, title="Page not found",
        message="The page you're looking for doesn't exist.",
    ), 404


@app.errorhandler(413)
def payload_too_large(error):
    if _wants_json():
        return jsonify({"error": "Upload too large (max 16 MB)."}), 413
    return render_template(
        "error.html", code=413, title="Upload too large",
        message="That file is larger than the 16 MB limit.",
    ), 413


@app.errorhandler(500)
def internal_error(error):
    try:
        db.session.rollback()
    except Exception:
        pass
    if _wants_json():
        return jsonify({"error": "Something went wrong. Please try again."}), 500
    return render_template(
        "error.html", code=500, title="Something went wrong",
        message="An unexpected error occurred. Please try again.",
    ), 500


@app.errorhandler(CSRFError)
def csrf_error(error):
    if _wants_json():
        return jsonify({"error": "Your session expired. Please refresh the page and try again."}), 400
    return render_template(
        "error.html", code=400, title="Session expired",
        message="Your session expired. Please refresh the page and try again.",
    ), 400

@app.route("/health")
def health():
    # Actually touch the database so platform health checks fail loudly when
    # the app can boot but cannot reach its database.
    try:
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok"}, 200
    except Exception:
        app.logger.exception("Health check failed")
        return {"status": "error", "database": "unavailable"}, 503

@app.route("/")
def home():
    if not g.user_id:
        return render_template("landing.html")
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    if not g.user_id:
        return redirect(url_for("auth.login"))

    contents = Content.query.filter_by(
        user_id=g.user_id,
        is_deleted=False
    ).order_by(Content.created_at.desc()).all()

    return render_template("dashboard.html", contents=contents)

if __name__ == "__main__":
    os.environ.setdefault("FLASK_ENV", "development")
    app.run(host="0.0.0.0", port=8000, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
