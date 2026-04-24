"""Connector-UI: Verbinden, Status und Trennen von Provider-Accounts.

Routen
------
GET  /connectors/                      – Liste aller Provider mit Status
GET  /connectors/<provider>/connect    – Formular für Credentials
POST /connectors/<provider>/connect    – Credentials speichern (upsert)
POST /connectors/<provider>/disconnect – Credential + Token-Dir löschen
"""
from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.connectors import PROVIDER_REGISTRY
from app.connectors.garmin import GarminConnector
from app.extensions import db
from app.models.connector import ConnectorCredential

from flask import Blueprint

connectors_bp = Blueprint("connectors", __name__, template_folder="../templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_provider_cls(provider: str):
    """Gibt die Provider-Klasse zurück oder bricht mit 404 ab."""
    cls = PROVIDER_REGISTRY.get(provider)
    if cls is None:
        abort(404)
    return cls


def _get_credential(user_id: int, provider: str) -> ConnectorCredential | None:
    return db.session.execute(
        db.select(ConnectorCredential).where(
            ConnectorCredential.user_id == user_id,
            ConnectorCredential.provider_type == provider,
        )
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@connectors_bp.route("/")
@login_required
def index():
    """Liste aller registrierten Provider mit Verbunden-Status."""
    providers = []
    for provider_type, cls in PROVIDER_REGISTRY.items():
        cred = _get_credential(current_user.id, provider_type)
        providers.append(
            {
                "provider_type": provider_type,
                "display_name": cls.display_name,
                "connected": cred is not None,
            }
        )
    return render_template("connectors/index.html", providers=providers)


@connectors_bp.route("/<provider>/connect", methods=["GET"])
@login_required
def connect_form(provider: str):
    """Formular für Connector-Credentials anzeigen."""
    cls = _get_provider_cls(provider)
    return render_template(
        "connectors/connect.html",
        provider_type=provider,
        display_name=cls.display_name,
        credential_fields=cls.credential_fields,
    )


@connectors_bp.route("/<provider>/connect", methods=["POST"])
@login_required
def connect_save(provider: str):
    """Credentials speichern (verschlüsselt via _JsonFernetField, Upsert)."""
    cls = _get_provider_cls(provider)

    # Nur bekannte Felder aus dem Formular übernehmen – niemals beliebige Input-Keys
    credentials = {
        field: request.form.get(field, "")
        for field in cls.credential_fields
    }

    # Pflichtfelder prüfen (kein leeres Credential speichern)
    if any(v == "" for v in credentials.values()):
        flash("Bitte alle Felder ausfüllen.", "danger")
        return redirect(url_for("connectors.connect_form", provider=provider))

    existing = _get_credential(current_user.id, provider)
    if existing is None:
        cred = ConnectorCredential(
            user_id=current_user.id,
            provider_type=provider,
            credentials=credentials,
        )
        db.session.add(cred)
    else:
        existing.credentials = credentials

    db.session.commit()

    flash(f"{cls.display_name} erfolgreich verbunden.", "success")
    return redirect(url_for("connectors.index"))


@connectors_bp.route("/<provider>/disconnect", methods=["POST"])
@login_required
def disconnect(provider: str):
    """Credential löschen und (bei Garmin) Token-Dir entfernen."""
    cls = _get_provider_cls(provider)

    cred = _get_credential(current_user.id, provider)
    if cred is None:
        flash(f"{cls.display_name} war nicht verbunden.", "warning")
        return redirect(url_for("connectors.index"))

    # Provider-spezifisches Cleanup (z.B. Token-Dir löschen)
    if provider == GarminConnector.provider_type:
        connector = GarminConnector(user_id=current_user.id)
        connector.disconnect()

    db.session.delete(cred)
    db.session.commit()

    flash(f"{cls.display_name} getrennt.", "success")
    return redirect(url_for("connectors.index"))
