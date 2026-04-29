from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db, limiter

settings_bp = Blueprint("settings", __name__, template_folder="../templates")

_MIN_NICKNAME_LENGTH = 3
_MAX_NICKNAME_LENGTH = 30
_MIN_PASSWORD_LENGTH = 8


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def profile():
    error = None
    if request.method == "POST":
        nickname = request.form.get("nickname", "").strip()
        if len(nickname) < _MIN_NICKNAME_LENGTH:
            error = f"Spitzname muss mindestens {_MIN_NICKNAME_LENGTH} Zeichen lang sein."
        elif len(nickname) > _MAX_NICKNAME_LENGTH:
            error = f"Spitzname darf maximal {_MAX_NICKNAME_LENGTH} Zeichen lang sein."
        else:
            current_user.nickname = nickname
            try:
                db.session.commit()
                flash("Spitzname gespeichert.")
                return redirect(url_for("settings.profile"))
            except IntegrityError:
                db.session.rollback()
                error = "Dieser Spitzname ist bereits vergeben."

    return render_template("settings/profile.html", error=error)


@settings_bp.route("/change-password", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
def change_password():
    old_password = request.form.get("old_password", "")
    new_password = request.form.get("new_password", "")

    if not current_user.check_password(old_password):
        flash("Aktuelles Passwort ist falsch.", "danger")
    elif len(new_password) < _MIN_PASSWORD_LENGTH:
        flash(f"Neues Passwort muss mindestens {_MIN_PASSWORD_LENGTH} Zeichen lang sein.", "danger")
    else:
        current_user.set_password(new_password)
        db.session.commit()
        flash("Passwort erfolgreich geändert.", "success")

    return redirect(url_for("settings.profile"))
