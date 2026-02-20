import os
from flask import Flask, redirect, url_for, session, render_template
from extensions import db
from auth import auth_bp
from content import content_bp
from models import Content
from search import search_bp
from chat import chat_bp
from remix import remix_bp
from settings import settings_bp


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///vault.db"
)
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
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)



