from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import re
from supabase_client import supabase

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
        if supabase is None:
            flash("Supabase is not configured. Please check your .env file.", "error")
            return redirect(url_for("auth.signup"))
            
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or len(name) > 100:
            flash("Name is required", "error")
            return redirect(url_for("auth.signup"))

        if not email or not validate_email(email):
            flash("Please enter a valid email address", "error")
            return redirect(url_for("auth.signup"))

        pwd_errors = validate_password(password)
        if pwd_errors:
            for err in pwd_errors:
                flash(err, "error")
            return redirect(url_for("auth.signup"))

        try:
            # Supabase Auth Signup
            # We store the name in user_metadata
            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {"name": name}
                }
            })
            
            if response.user:
                # Signup successful
                # Note: Supabase might require email confirmation depending on project settings.
                # If confirmation is off, the user is logged in immediately.
                if response.session:
                    session["supabase_token"] = response.session.access_token
                    session["user_id"] = response.user.id
                    session["user_name"] = response.user.user_metadata.get("name", "Creator")
                    flash("Signup successful!", "success")
                    return redirect(url_for("settings.onboarding"))
                else:
                    flash("Please check your email to confirm your account.", "info")
                    return redirect(url_for("auth.login"))
            else:
                flash("Signup failed. Please try again.", "error")
        except Exception as e:
            error_msg = str(e)
            if "User already registered" in error_msg:
                flash("User already exists", "error")
            else:
                print(f"Signup error: {e}")
                flash("Error signing up. Please try again later.", "error")
            return redirect(url_for("auth.signup"))

    return render_template("signup.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if supabase is None:
            flash("Supabase is not configured. Please check your .env file.", "error")
            return redirect(url_for("auth.login"))
            
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password", "error")
            return redirect(url_for("auth.login"))

        try:
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.session and response.user:
                session["supabase_token"] = response.session.access_token
                session["user_id"] = response.user.id
                session["user_name"] = response.user.user_metadata.get("name", "Creator")
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid email or password", "error")
        except Exception as e:
            print(f"Login error: {e}")
            flash("Invalid email or password", "error")
            return redirect(url_for("auth.login"))

    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    try:
        supabase.auth.sign_out()
    except:
        pass
    session.clear()
    return redirect(url_for("home"))
