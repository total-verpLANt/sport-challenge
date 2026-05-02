import logging
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

logger = logging.getLogger(__name__)

from sqlalchemy import or_

from app.extensions import db
from app.models.activity import Activity
from app.models.bonus import BonusChallengeEntry
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.connector import ConnectorCredential
from app.models.penalty import PenaltyOverride
from app.models.sick_week import SickWeek
from app.models.user import User
from app.services.mailer import MailgunError, get_mailer
from app.utils.decorators import admin_required
from app.utils.uploads import delete_media_files, delete_upload

_MIN_PASSWORD_LENGTH = 8

admin_bp = Blueprint("admin", __name__, template_folder="../templates")


@admin_bp.route("/users")
@admin_required
def users():
    all_users = db.session.execute(
        db.select(User).order_by(User.is_approved, User.created_at)
    ).scalars().all()
    pending_count = db.session.execute(
        db.select(func.count()).select_from(User).where(User.is_approved == False)  # noqa: E712
    ).scalar()
    return render_template("admin/users.html", users=all_users, pending_count=pending_count)


@admin_bp.route("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    user = db.get_or_404(User, user_id)
    connectors = ConnectorCredential.query.filter_by(user_id=user.id).all()
    has_challenges = Challenge.query.filter_by(created_by_id=user.id).first() is not None
    return render_template(
        "admin/user_detail.html",
        user=user,
        connectors=connectors,
        has_challenges=has_challenges,
    )


@admin_bp.route("/users/<int:user_id>/approve", methods=["POST"])
@admin_required
def approve_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        flash("Benutzer nicht gefunden.")
        return redirect(url_for("admin.users"))
    if user.id == current_user.id:
        flash("Eigenen Account kann man nicht über dieses Formular verwalten.")
        return redirect(url_for("admin.users"))
    user.is_approved = True
    user.approved_at = datetime.now(timezone.utc)
    user.approved_by_id = current_user.id
    db.session.commit()
    _send_approval_mail(user)
    flash(f"Benutzer {user.display_name} ({user.email}) wurde freigeschaltet.")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/reject", methods=["POST"])
@admin_required
def reject_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        flash("Benutzer nicht gefunden.")
        return redirect(url_for("admin.users"))
    if user.id == current_user.id:
        flash("Eigenen Account kann man nicht über dieses Formular verwalten.")
        return redirect(url_for("admin.users"))
    name = user.display_name
    email = user.email
    db.session.delete(user)
    db.session.commit()
    flash(f"Benutzer {name} ({email}) wurde abgelehnt und gelöscht.")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/suspend", methods=["POST"])
@admin_required
def suspend_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("Eigenes Konto kann nicht gesperrt werden.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))
    user.is_approved = False
    db.session.commit()
    flash(f"Konto {user.display_name} gesperrt.", "warning")
    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/unsuspend", methods=["POST"])
@admin_required
def unsuspend_user(user_id):
    user = db.get_or_404(User, user_id)
    user.is_approved = True
    db.session.commit()
    flash(f"Konto {user.display_name} entsperrt.", "success")
    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def reset_password(user_id):
    user = db.get_or_404(User, user_id)
    new_password = request.form.get("new_password", "")
    if len(new_password) < _MIN_PASSWORD_LENGTH:
        flash(f"Passwort muss mindestens {_MIN_PASSWORD_LENGTH} Zeichen lang sein.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))
    user.set_password(new_password)
    db.session.commit()
    flash(f"Passwort für {user.display_name} zurückgesetzt.", "success")
    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/toggle-admin", methods=["POST"])
@admin_required
def toggle_admin(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        flash("Benutzer nicht gefunden.")
        return redirect(url_for("admin.users"))
    if user.id == current_user.id:
        flash("Du kannst dir nicht selbst die Admin-Rolle entziehen.")
        return redirect(url_for("admin.users"))
    if not user.is_approved:
        flash("Nur freigeschaltete Benutzer können zum Admin befördert werden.")
        return redirect(url_for("admin.users"))
    if user.is_admin:
        admin_count = db.session.execute(
            db.select(func.count()).select_from(User).where(User.role == "admin")
        ).scalar()
        if admin_count <= 1:
            flash("Mindestens ein Admin muss bestehen bleiben.")
            return redirect(url_for("admin.users"))
        user.role = "user"
        flash(f"{user.display_name} ist kein Admin mehr.")
    else:
        user.role = "admin"
        flash(f"{user.display_name} wurde zum Admin befördert.")
    db.session.commit()
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = db.get_or_404(User, user_id)

    # Self-Delete blockieren
    if user.id == current_user.id:
        flash("Eigenes Konto kann nicht gelöscht werden.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))

    # Last-Admin-Guard
    if user.is_admin:
        admin_count = db.session.scalar(
            db.select(func.count()).select_from(User).where(User.role == "admin")
        )
        if admin_count <= 1:
            flash("Letzter Admin kann nicht gelöscht werden.", "danger")
            return redirect(url_for("admin.user_detail", user_id=user_id))

    # Block wenn User Challenges erstellt hat
    if Challenge.query.filter_by(created_by_id=user.id).first():
        flash("User hat Challenges erstellt – bitte zuerst Challenges löschen oder übertragen.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))

    # Zweistufige Bestätigung: E-Mail-Prüfung serverseitig
    confirm_email = request.form.get("confirm_email", "").strip()
    if confirm_email != user.email:
        flash("E-Mail-Bestätigung stimmt nicht überein.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))

    # Cascade-Löschen in Reihenfolge
    BonusChallengeEntry.query.filter_by(user_id=user.id).delete()
    PenaltyOverride.query.filter(
        or_(PenaltyOverride.user_id == user.id, PenaltyOverride.set_by_id == user.id)
    ).delete()
    SickWeek.query.filter_by(user_id=user.id).delete()
    for _act in Activity.query.filter_by(user_id=user.id).all():
        delete_media_files(_act.media)
        if _act.screenshot_path:
            delete_upload(_act.screenshot_path)
        db.session.delete(_act)
    ChallengeParticipation.query.filter_by(user_id=user.id).delete()
    ConnectorCredential.query.filter_by(user_id=user.id).delete()

    display = user.display_name
    db.session.delete(user)
    db.session.commit()
    flash(f"Konto {display} wurde gelöscht.", "success")
    return redirect(url_for("admin.users"))


def _send_approval_mail(user: User) -> None:
    """Sendet Freischaltungs-Bestätigung an den User. Fehler werden nur geloggt."""
    login_url = url_for("auth.login", _external=True)
    body = render_template(
        "email/user_approved.txt",
        display_name=user.display_name,
        login_url=login_url,
    )
    try:
        get_mailer().send(
            to=user.email,
            subject="[Sport Challenge] Dein Konto wurde freigeschaltet",
            text=body,
            tags=["user-approved"],
        )
    except MailgunError as exc:
        logger.error("Approval-Mail an %s fehlgeschlagen: %s", user.email, exc)
