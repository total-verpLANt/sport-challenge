from datetime import datetime, timedelta, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from email_validator import validate_email, EmailNotValidError

from app.extensions import db, limiter
from app.models.user import User

auth_bp = Blueprint("auth", __name__, template_folder="../templates")

_MAX_FAILED_ATTEMPTS = 10
_LOCKOUT_DURATION = timedelta(minutes=10)
_MIN_PASSWORD_LENGTH = 8


@auth_bp.route("/login", methods=["GET", "POST"])
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
            now = datetime.now(timezone.utc)
            if user and user.locked_until:
                # SQLite liefert naive datetimes → als UTC behandeln
                lu = user.locked_until if user.locked_until.tzinfo else user.locked_until.replace(tzinfo=timezone.utc)
                if lu > now:
                    remaining = int((lu - now).total_seconds() / 60) + 1
                    error = f"Konto gesperrt – bitte {remaining} Minute(n) warten."
                    user = None  # verhindert Passwort-Check auf gesperrtem Konto
            if user is not None:
                if user.check_password(password):
                    user.failed_login_attempts = 0
                    user.locked_until = None
                    db.session.commit()
                    if not user.is_approved:
                        error = "Konto wartet auf Admin-Freigabe."
                    else:
                        login_user(user)
                        return redirect(url_for("activities.week_view"))
                else:
                    user.failed_login_attempts += 1
                    if user.failed_login_attempts >= _MAX_FAILED_ATTEMPTS:
                        user.locked_until = datetime.now(timezone.utc) + _LOCKOUT_DURATION
                    db.session.commit()
                    error = "Ungültige Anmeldedaten."
            elif error is None:
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
        elif len(password) < _MIN_PASSWORD_LENGTH:
            error = f"Passwort muss mindestens {_MIN_PASSWORD_LENGTH} Zeichen lang sein."
        else:
            try:
                result = validate_email(email, check_deliverability=False)
                email = result.normalized
            except EmailNotValidError:
                error = "Ungültige E-Mail-Adresse."
            if error is None:
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
