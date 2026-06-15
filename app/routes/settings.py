import logging

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db, limiter
from app.models.activity import Activity
from app.models.bonus import BonusChallengeEntry
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.connector import ConnectorCredential
from app.models.penalty import PenaltyOverride
from app.models.sick_period import SickPeriod, SickPeriodLike
from app.models.user import User
from app.utils.uploads import delete_media_files, delete_upload

logger = logging.getLogger(__name__)

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


@settings_bp.route("/delete-account", methods=["POST"])
@login_required
@limiter.limit("3 per hour")
def delete_account():
    password = request.form.get("password", "")

    if not password or not current_user.check_password(password):
        flash("Passwort ist falsch.", "danger")
        return redirect(url_for("settings.profile"))

    # Last-Admin-Guard
    if current_user.is_admin:
        admin_count = db.session.scalar(
            db.select(func.count()).select_from(User).where(User.role == "admin")
        )
        if admin_count <= 1:
            flash("Als letzter Admin kann das Konto nicht gelöscht werden.", "danger")
            return redirect(url_for("settings.profile"))

    # Guard: User hat Challenges erstellt
    if Challenge.query.filter_by(created_by_id=current_user.id).first():
        flash("Du hast Challenges erstellt – bitte diese zuerst löschen oder übertragen.", "danger")
        return redirect(url_for("settings.profile"))

    user_id = current_user.id
    display = current_user.display_name

    BonusChallengeEntry.query.filter_by(user_id=user_id).delete()
    PenaltyOverride.query.filter(
        or_(PenaltyOverride.user_id == user_id, PenaltyOverride.set_by_id == user_id)
    ).delete()
    _own_sp_ids = [sp.id for sp in SickPeriod.query.filter_by(user_id=user_id).all()]
    if _own_sp_ids:
        SickPeriodLike.query.filter(
            SickPeriodLike.sick_period_id.in_(_own_sp_ids)
        ).delete(synchronize_session="fetch")
    SickPeriodLike.query.filter_by(user_id=user_id).delete()
    SickPeriod.query.filter_by(user_id=user_id).delete()
    for act in Activity.query.filter_by(user_id=user_id).all():
        delete_media_files(act.media)
        if act.screenshot_path:
            delete_upload(act.screenshot_path)
        db.session.delete(act)
    ChallengeParticipation.query.filter_by(user_id=user_id).delete()
    ConnectorCredential.query.filter_by(user_id=user_id).delete()

    user = db.session.get(User, user_id)
    db.session.delete(user)
    db.session.commit()

    logout_user()
    logger.info("Self-Delete: Konto %s (id=%s) gelöscht.", display, user_id)
    flash("Dein Konto wurde gelöscht.", "success")
    return redirect(url_for("auth.login"))


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
