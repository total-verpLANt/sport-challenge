"""Strava OAuth2 Authorization Code Flow.

Routen
------
GET /connectors/strava/oauth/start    – Redirect zu Strava-Autorisierung
GET /connectors/strava/oauth/callback – Code-Exchange, Token in DB speichern
"""
from __future__ import annotations

import secrets

from flask import Blueprint, current_app, flash, redirect, request, session, url_for
from flask_login import current_user, login_required
from stravalib.client import Client

from app.extensions import db
from app.models.connector import ConnectorCredential

strava_oauth_bp = Blueprint("strava_oauth", __name__)


@strava_oauth_bp.route("/connectors/strava/oauth/start")
@login_required
def oauth_start():
    """Leitet den User zur Strava-Autorisierungsseite weiter."""
    state = secrets.token_urlsafe(16)
    session["strava_oauth_state"] = state

    client = Client()
    redirect_uri = url_for("strava_oauth.oauth_callback", _external=True)
    authorize_url = client.authorization_url(
        client_id=current_app.config["STRAVA_CLIENT_ID"],
        redirect_uri=redirect_uri,
        scope=["activity:read"],
        state=state,
    )
    return redirect(authorize_url)


@strava_oauth_bp.route("/connectors/strava/oauth/callback")
@login_required
def oauth_callback():
    """Verarbeitet den Strava-Callback: Code-Exchange und Token-Speicherung."""
    error = request.args.get("error")
    if error:
        flash(f"Strava-Verbindung abgelehnt: {error}", "danger")
        return redirect(url_for("connectors.index"))

    state = request.args.get("state", "")
    expected = session.pop("strava_oauth_state", None)
    if not expected or state != expected:
        flash("Ungültiger OAuth-State. Bitte erneut versuchen.", "danger")
        return redirect(url_for("connectors.index"))

    code = request.args.get("code", "")
    tmp = Client()
    token_response = tmp.exchange_code_for_token(
        client_id=current_app.config["STRAVA_CLIENT_ID"],
        client_secret=current_app.config["STRAVA_CLIENT_SECRET"],
        code=code,
    )
    credentials = {
        "access_token": token_response["access_token"],
        "refresh_token": token_response["refresh_token"],
        "expires_at": int(token_response["expires_at"]),
    }

    existing = db.session.execute(
        db.select(ConnectorCredential).where(
            ConnectorCredential.user_id == current_user.id,
            ConnectorCredential.provider_type == "strava",
        )
    ).scalar_one_or_none()

    if existing is None:
        db.session.add(ConnectorCredential(
            user_id=current_user.id,
            provider_type="strava",
            credentials=credentials,
        ))
    else:
        existing.credentials = credentials

    db.session.commit()
    flash("Strava erfolgreich verbunden.", "success")
    return redirect(url_for("connectors.index"))
