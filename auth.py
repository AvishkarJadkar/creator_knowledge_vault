from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

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
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid credentials", "error")
            return redirect(url_for("auth.login"))

        session["user_id"] = user.id
        session["user_name"] = user.name
        return redirect(url_for("dashboard"))

    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
