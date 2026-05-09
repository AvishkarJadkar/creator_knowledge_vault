from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import re
import firebase_client

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
        if not firebase_client.FIREBASE_API_KEY:
            flash("Firebase is not configured. Please check your .env file.", "error")
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
            print("DEBUG: Attempting signup via Firebase Auth")
            response = firebase_client.sign_up(email, password, name)
            
            session["firebase_token"] = response["session"]["access_token"]
            session["user_id"] = response["user"]["id"]
            session["user_name"] = response["user"]["user_metadata"]["name"]
            
            flash("Signup successful!", "success")
            return redirect(url_for("settings.onboarding"))
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            with open("scratch/error.log", "w") as f:
                f.write(traceback.format_exc())
            error_msg = str(e)
            print(f"Signup error: {e}", flush=True)
            
            if "EMAIL_EXISTS" in error_msg:
                flash("User already exists", "error")
            else:
                flash(f"Signup Failed: {error_msg}", "error")
                
            return redirect(url_for("auth.signup"))

    return render_template("signup.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not firebase_client.FIREBASE_API_KEY:
            flash("Firebase is not configured. Please check your .env file.", "error")
            return redirect(url_for("auth.login"))
            
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password", "error")
            return redirect(url_for("auth.login"))

        try:
            print("DEBUG: Attempting login via Firebase Auth")
            response = firebase_client.sign_in_with_password(email, password)
            
            session["firebase_token"] = response["session"]["access_token"]
            session["user_id"] = response["user"]["id"]
            session["user_name"] = response["user"]["user_metadata"]["name"]
            
            return redirect(url_for("dashboard"))
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = str(e)
            print(f"Login error: {e}", flush=True)
            
            if "INVALID_LOGIN_CREDENTIALS" in error_msg or "INVALID_PASSWORD" in error_msg or "EMAIL_NOT_FOUND" in error_msg:
                flash("Invalid email or password", "error")
            else:
                flash(f"Login Failed: {error_msg}", "error")
                
            return redirect(url_for("auth.login"))

    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    try:
        firebase_client.sign_out()
    except:
        pass
    session.clear()
    return redirect(url_for("home"))
