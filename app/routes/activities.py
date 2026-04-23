from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, current_app, render_template, request, session

from app.garmin.client import GarminClient
from app.routes.auth import login_required

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

    error = None
    activities = []
    try:
        client = GarminClient(current_app.config["GARMIN_TOKEN_DIR"])
        client.reconnect(session["garmin_email"])
        raw = client.get_week_activities(monday, sunday)
        activities = [
            {
                "date": a.get("startTimeLocal", "")[:10],
                "name": a.get("activityName", "–"),
                "type": a.get("activityType", {}).get("typeKey", "–"),
                "duration": GarminClient.format_duration(a.get("duration", 0)),
                "distance": (
                    GarminClient.format_distance(a["distance"])
                    if a.get("distance")
                    else "–"
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
