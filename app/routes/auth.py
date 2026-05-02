import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func

from email_validator import validate_email, EmailNotValidError

from app.extensions import db, limiter
from app.models.user import User
from app.services.mailer import MailgunError, get_mailer

logger = logging.getLogger(__name__)

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
                        if user.nickname is None:
                            flash("Willkommen! Gib dir einen Spitznamen – er wird überall angezeigt.")
                            return redirect(url_for("settings.profile"))
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
                        flash("Willkommen! Gib dir einen Spitznamen – er wird überall angezeigt.")
                        return redirect(url_for("settings.profile"))
                    _notify_admins_new_user(user)
                    flash("Registrierung erfolgreich – warte auf Admin-Freigabe.")
                    return redirect(url_for("auth.login"))

    return render_template("auth/register.html", error=error)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


_RESET_TOKEN_MAX_AGE = 3600  # 1 Stunde
_RESET_SALT = "password-reset"


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per minute")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("activities.week_view"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        # Timing-sicheres Verhalten: gleiche Antwort ob E-Mail bekannt oder nicht
        user = None
        try:
            result = validate_email(email, check_deliverability=False)
            user = db.session.execute(
                db.select(User).filter_by(email=result.normalized)
            ).scalar_one_or_none()
        except EmailNotValidError:
            pass

        if user is not None:
            _send_password_reset_mail(user)

        flash("Falls ein Konto mit dieser E-Mail existiert, wurde ein Reset-Link versendet.", "info")
        return redirect(url_for("auth.forgot_password"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    from flask import current_app

    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        user_id = s.loads(token, salt=_RESET_SALT, max_age=_RESET_TOKEN_MAX_AGE)
    except SignatureExpired:
        flash("Der Reset-Link ist abgelaufen. Bitte fordere einen neuen an.", "danger")
        return redirect(url_for("auth.forgot_password"))
    except BadSignature:
        flash("Ungültiger Reset-Link.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = db.session.get(User, user_id)
    if user is None:
        flash("Benutzer nicht gefunden.", "danger")
        return redirect(url_for("auth.forgot_password"))

    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        if len(password) < _MIN_PASSWORD_LENGTH:
            error = f"Passwort muss mindestens {_MIN_PASSWORD_LENGTH} Zeichen lang sein."
        elif password != password2:
            error = "Passwörter stimmen nicht überein."
        else:
            user.set_password(password)
            db.session.commit()
            flash("Passwort erfolgreich geändert. Du kannst dich jetzt einloggen.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token, error=error)


def _send_password_reset_mail(user: User) -> None:
    """Sendet Reset-Mail. Fehler werden nur geloggt – kein Hinweis an den Client."""
    from flask import current_app

    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    token = s.dumps(user.id, salt=_RESET_SALT)
    reset_url = url_for("auth.reset_password", token=token, _external=True)

    body = render_template("email/password_reset.txt", reset_url=reset_url)
    try:
        get_mailer().send(
            to=user.email,
            subject="[Sport Challenge] Passwort zurücksetzen",
            text=body,
            tags=["password-reset"],
        )
    except MailgunError as exc:
        logger.error("Password-Reset-Mail an %s fehlgeschlagen: %s", user.email, exc)


def _notify_admins_new_user(new_user: User) -> None:
    """Sendet Admin-Benachrichtigung bei Neuregistrierung. Fehler werden nur geloggt."""
    admins = db.session.execute(
        db.select(User).filter_by(role="admin")
    ).scalars().all()
    if not admins:
        return

    admin_url = url_for("admin.users", _external=True)
    registered_at = new_user.created_at.strftime("%d.%m.%Y %H:%M UTC") if new_user.created_at else "unbekannt"

    body = render_template(
        "email/new_user_notification.txt",
        user_email=new_user.email,
        registered_at=registered_at,
        admin_url=admin_url,
    )
    try:
        mailer = get_mailer()
        for admin in admins:
            mailer.send(
                to=admin.email,
                subject="[Sport Challenge] Neuer Benutzer wartet auf Freigabe",
                text=body,
                tags=["admin-notification"],
            )
    except MailgunError as exc:
        logger.error("Admin-Benachrichtigung fehlgeschlagen: %s", exc)
