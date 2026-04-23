from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, current_app, render_template, request

from app.garmin.client import GarminClient

activities_bp = Blueprint("activities", __name__, template_folder="../templates")


def _get_week_bounds(ref: date) -> tuple[date, date]:
    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _get_garmin_client() -> GarminClient:
    return GarminClient(
        email=current_app.config["GARMIN_EMAIL"],
        password=current_app.config["GARMIN_PASSWORD"],
        token_dir=current_app.config["GARMIN_TOKEN_DIR"],
    )


@activities_bp.route("/week")
def week_view():
    offset = request.args.get("offset", 0, type=int)
    ref = date.today() + timedelta(weeks=offset)
    monday, sunday = _get_week_bounds(ref)

    error = None
    activities = []
    try:
        client = _get_garmin_client()
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
        ]
    except Exception as exc:
        error = str(exc)

    return render_template(
        "activities/week.html",
        activities=activities,
        monday=monday,
        sunday=sunday,
        offset=offset,
        error=error,
    )
