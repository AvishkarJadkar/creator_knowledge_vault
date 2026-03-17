import re
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__)


def validate_password(password):
    """Enforce minimum password security requirements."""
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one number")
    return errors


def validate_email(email):
    """Basic email format validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # --- SECURITY: Input validation ---
        if not name or len(name) > 100:
            flash("Name is required and must be under 100 characters", "error")
            return redirect(url_for("auth.signup"))

        if not email or not validate_email(email) or len(email) > 120:
            flash("Please enter a valid email address", "error")
            return redirect(url_for("auth.signup"))

        # --- SECURITY: Password strength validation ---
        pwd_errors = validate_password(password)
        if pwd_errors:
            for err in pwd_errors:
                flash(err, "error")
            return redirect(url_for("auth.signup"))

        if User.query.filter_by(email=email).first():
            flash("User already exists", "error")
            return redirect(url_for("auth.signup"))

        user = User(name=name, email=email)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id
        session["user_name"] = user.name
        return redirect(url_for("dashboard"))

    return render_template("signup.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password", "error")
            return redirect(url_for("auth.login"))

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            # --- SECURITY: Generic error message to prevent user enumeration ---
            flash("Invalid email or password", "error")
            return redirect(url_for("auth.login"))

        session["user_id"] = user.id
        session["user_name"] = user.name
        return redirect(url_for("dashboard"))

    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
