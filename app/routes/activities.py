from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.connectors import PROVIDER_REGISTRY
from app.extensions import db
from app.models.connector import ConnectorCredential

activities_bp = Blueprint("activities", __name__, template_folder="../templates")


def _get_week_bounds(ref: date) -> tuple[date, date]:
    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


@activities_bp.route("/week")
@login_required
def week_view():
    offset = request.args.get("offset", 0, type=int)
    filter_short = request.args.get("filter_short", "1")
    ref = date.today() + timedelta(weeks=offset)
    monday, sunday = _get_week_bounds(ref)

    # Provider-Auswahl: ?provider=strava / ?provider=garmin, Fallback auf ersten verbundenen
    provider_type = request.args.get("provider")
    if provider_type:
        cred = ConnectorCredential.query.filter_by(
            user_id=current_user.id, provider_type=provider_type
        ).first()
        if cred is None:
            return redirect(url_for("connectors.index"))
    else:
        cred = ConnectorCredential.query.filter_by(
            user_id=current_user.id
        ).first()
        if cred is None:
            return redirect(url_for("connectors.index"))
        provider_type = cred.provider_type

    connector_cls = PROVIDER_REGISTRY.get(provider_type)
    if connector_cls is None:
        abort(404)
    connector = connector_cls(user_id=current_user.id)

    error = None
    activities = []
    try:
        connector.connect(cred.credentials)
        # Refresh-Persistenz: generisch via get_token_updates()
        updates = connector.get_token_updates()
        if updates:
            updated = dict(cred.credentials)
            updated.update(updates)
            cred.credentials = updated
            db.session.commit()
        raw = connector.get_activities(monday, sunday)
        activities = [
            {
                "date": a.get("startTimeLocal", "")[:10],
                "name": a.get("activityName", "–"),
                "type": a.get("activityType", {}).get("typeKey", "–"),
                "duration": _format_duration(a.get("duration", 0)),
                "distance": (
                    _format_distance(a["distance"]) if a.get("distance") else "–"
                ),
                "avg_hr": a.get("averageHR", "–"),
                "calories": a.get("calories", "–"),
            }
            for a in raw
            if filter_short != "1" or a.get("duration", 0) >= 1800
        ]
    except Exception as exc:
        error = str(exc)

    return render_template(
        "activities/week.html",
        activities=activities,
        monday=monday,
        sunday=sunday,
        offset=offset,
        filter_short=filter_short,
        error=error,
    )


def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    return f"{h}:{m:02d}:{s:02d}"


def _format_distance(meters: float) -> str:
    return f"{meters / 1000:.2f} km"
