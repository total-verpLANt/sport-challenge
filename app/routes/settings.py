from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db

settings_bp = Blueprint("settings", __name__, template_folder="../templates")

_MIN_NICKNAME_LENGTH = 3
_MAX_NICKNAME_LENGTH = 30


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
