from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, url_for
from sqlalchemy import func

from app.extensions import db
from app.models.user import User
from app.utils.decorators import admin_required

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


@admin_bp.route("/users/<int:user_id>/approve", methods=["POST"])
@admin_required
def approve_user(user_id):
    from flask_login import current_user
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
    flash(f"Benutzer {user.display_name} ({user.email}) wurde freigeschaltet.")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/reject", methods=["POST"])
@admin_required
def reject_user(user_id):
    from flask_login import current_user
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


@admin_bp.route("/users/<int:user_id>/toggle-admin", methods=["POST"])
@admin_required
def toggle_admin(user_id):
    from flask_login import current_user
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
