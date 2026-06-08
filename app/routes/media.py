"""Login-geschützte Auslieferung hochgeladener Medien (Issue 1ye).

Uploads liegen außerhalb von ``static`` (siehe ``config.UPLOAD_FOLDER``) und sind
damit nicht mehr anonym per Direkt-URL abrufbar. Diese Routen liefern Medien nur
für angemeldete Nutzer aus – referenziert wird stets über die DB-ID, nie über den
rohen Dateinamen aus dem Request.
"""

from pathlib import Path

from flask import Blueprint, abort, current_app, send_from_directory
from flask_login import login_required

from app.extensions import db
from app.models.activity import Activity, ActivityMedia

media_bp = Blueprint("media", __name__)


def _serve(stored_path: str | None):
    """Liefert eine Datei aus dem Upload-Verzeichnis aus.

    ``stored_path`` ist der in der DB gespeicherte Wert (z. B. ``uploads/<uuid>.jpg``).
    Nur der reine Dateiname wird verwendet – das verhindert Path-Traversal über
    manipulierte DB-/Pfadwerte, zusätzlich zum safe_join in send_from_directory.
    """
    if not stored_path:
        abort(404)
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    filename = Path(stored_path).name
    response = send_from_directory(upload_dir, filename)
    # Härtung: kein MIME-Sniffing, kein Shared-Cache (privat pro Nutzer).
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response


@media_bp.route("/activity/<int:media_id>")
@login_required
def activity_media(media_id: int):
    """Liefert ein ActivityMedia-Objekt (Bild/Video) aus."""
    media = db.get_or_404(ActivityMedia, media_id)
    return _serve(media.file_path)


@media_bp.route("/screenshot/<int:activity_id>")
@login_required
def activity_screenshot(activity_id: int):
    """Liefert den Legacy-Screenshot einer Activity aus."""
    activity = db.get_or_404(Activity, activity_id)
    return _serve(activity.screenshot_path)
