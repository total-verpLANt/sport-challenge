"""Routen für das Notification-Center (Navbar-Glocke, Ticket wsco).

Lesen läuft über einen GET-Redirect (`/<id>/go`): markiert die Notification
als gelesen und leitet zum Ziel weiter – ohne JS, ohne Navigations-Race.
Löschen (einzeln/alle) läuft über CSRF-geschützte POSTs und gibt den neuen
Ungelesen-Zähler als JSON zurück, damit das Frontend den Badge aktualisiert.
"""
from flask import Blueprint, jsonify, redirect, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models.notification import Notification
from app.services import notifications as notif_service

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/<int:notification_id>/go")
@login_required
def go(notification_id: int):
    """Markiert die Notification als gelesen und leitet zum Ziel weiter.

    Nur die eigene Notification (user_id-Filter). Fallback: Dashboard.
    Non-destruktiv (setzt nur read_at) → CSRF-unkritisch trotz GET.
    """
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        return redirect(url_for("dashboard.index"))

    notif_service.mark_read(current_user.id, ids=[notification_id])

    return redirect(_safe_target(notification.link_url))


def _safe_target(link_url: str | None) -> str:
    """Open-Redirect-Guard: nur interne Pfade zulassen, sonst Dashboard.

    Erlaubt ausschließlich Pfade, die mit einem einzelnen '/' beginnen
    (nicht '//' oder '/\\' → protocol-relative/externe Ziele). Defense-in-
    depth, falls je ein Auslöser eine fremde URL in link_url schriebe.
    """
    fallback = url_for("dashboard.index")
    if not link_url or not link_url.startswith("/"):
        return fallback
    if link_url.startswith("//") or link_url.startswith("/\\"):
        return fallback
    return link_url


@notifications_bp.route("/<int:notification_id>/delete", methods=["POST"])
@login_required
def delete(notification_id: int):
    """Löscht eine einzelne Notification (nur eigene)."""
    notif_service.delete_notification(current_user.id, notification_id)
    return jsonify({"unread_count": notif_service.unread_count(current_user.id)})


@notifications_bp.route("/delete-all", methods=["POST"])
@login_required
def delete_all():
    """Löscht alle Notifications des Users."""
    deleted = notif_service.delete_all(current_user.id)
    return jsonify({"deleted": deleted, "unread_count": 0})
