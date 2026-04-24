from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from app.extensions import db, limiter
from app.models.user import User

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("activities.week_view"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not email or not password:
            error = "E-Mail und Passwort sind erforderlich."
        else:
            user = db.session.execute(
                db.select(User).filter_by(email=email)
            ).scalar_one_or_none()
            if user and user.check_password(password):
                if not user.is_approved:
                    error = "Konto wartet auf Admin-Freigabe."
                else:
                    login_user(user)
                    return redirect(url_for("activities.week_view"))
            else:
                error = "Ungültige Anmeldedaten."

    return render_template("auth/login.html", error=error)


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("3 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("activities.week_view"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not email or not password:
            error = "E-Mail und Passwort sind erforderlich."
        else:
            existing = db.session.execute(
                db.select(User).filter_by(email=email)
            ).scalar_one_or_none()
            if existing:
                error = "Diese E-Mail ist bereits registriert."
            else:
                user = User(email=email)
                user.set_password(password)
                is_first_user = db.session.execute(
                    db.select(func.count()).select_from(User)
                ).scalar() == 0
                if is_first_user:
                    user.role = "admin"
                    user.is_approved = True
                db.session.add(user)
                db.session.commit()
                if is_first_user:
                    login_user(user)
                    return redirect(url_for("activities.week_view"))
                flash("Registrierung erfolgreich – warte auf Admin-Freigabe.")
                return redirect(url_for("auth.login"))

    return render_template("auth/register.html", error=error)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
