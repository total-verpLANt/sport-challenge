from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.connectors import PROVIDER_REGISTRY
from app.extensions import db
from app.models.activity import Activity, ActivityMedia
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.connector import ConnectorCredential
from app.models.user import User
from app.utils.uploads import delete_media_files, delete_upload, get_media_type, save_upload

challenge_activities_bp = Blueprint(
    "challenge_activities", __name__, template_folder="../templates"
)


def _get_week_bounds(offset: int = 0) -> tuple[date, date]:
    """Return (monday, sunday) for the current week + offset weeks."""
    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _active_participation():
    """Return the current user's accepted ChallengeParticipation, or None."""
    return (
        db.session.execute(
            db.select(ChallengeParticipation).where(
                ChallengeParticipation.user_id == current_user.id,
                ChallengeParticipation.status == "accepted",
            )
        )
        .scalars()
        .first()
    )


@challenge_activities_bp.route("/log", methods=["GET"])
@login_required
def log_form():
    participation = _active_participation()
    if participation is None:
        flash("Du nimmst aktuell an keiner Challenge teil.")
        return redirect(url_for("challenges.index"))
    today = date.today().isoformat()
    return render_template("activities/log.html", today=today, participation=participation)


@challenge_activities_bp.route("/log", methods=["POST"])
@login_required
def log_submit():
    participation = _active_participation()
    if participation is None:
        flash("Du nimmst aktuell an keiner Challenge teil.")
        return redirect(url_for("challenges.index"))

    # Read form data
    raw_date = request.form.get("activity_date", "").strip()
    raw_duration = request.form.get("duration_minutes", "").strip()
    sport_type = request.form.get("sport_type", "").strip()
    notes_raw = request.form.get("notes", "").strip()
    if len(notes_raw) > 2000:
        flash("Die Trainingsnotiz darf maximal 2000 Zeichen lang sein.")
        return redirect(url_for("challenge_activities.log_form"))
    notes = notes_raw or None

    # Validate date
    try:
        activity_date = date.fromisoformat(raw_date)
    except ValueError:
        flash("Ungültiges Datum.")
        return redirect(url_for("challenge_activities.log_form"))

    challenge = participation.challenge
    if not (challenge.start_date <= activity_date <= challenge.end_date):
        flash(
            f"Datum muss innerhalb der Challenge-Periode liegen "
            f"({challenge.start_date} – {challenge.end_date})."
        )
        return redirect(url_for("challenge_activities.log_form"))

    # Validate duration
    try:
        duration_minutes = int(raw_duration)
        if duration_minutes <= 0:
            raise ValueError
    except ValueError:
        flash("Dauer muss eine positive Zahl sein.")
        return redirect(url_for("challenge_activities.log_form"))

    # Validate sport type
    if not sport_type:
        flash("Bitte Sportart angeben.")
        return redirect(url_for("challenge_activities.log_form"))

    # Optional media upload (mehrere Dateien)
    media_files = request.files.getlist("media")
    saved_media = []
    for f in media_files:
        if f and f.filename:
            path = save_upload(f)
            if path is None:
                flash("Ungültiges Dateiformat (erlaubt: JPG, PNG, WebP, MP4, MOV, WebM, max. 50 MB).")
                return redirect(url_for("challenge_activities.log_form"))
            saved_media.append((path, get_media_type(f.filename), f.filename))

    activity = Activity(
        user_id=current_user.id,
        challenge_id=participation.challenge_id,
        activity_date=activity_date,
        duration_minutes=duration_minutes,
        sport_type=sport_type,
        source="manual",
        notes=notes,
    )
    db.session.add(activity)
    db.session.flush()
    for file_path, media_type, orig_name in saved_media:
        db.session.add(ActivityMedia(
            activity_id=activity.id,
            file_path=file_path,
            media_type=media_type,
            original_filename=orig_name,
            file_size_bytes=0,
        ))
    db.session.commit()

    flash("Aktivität wurde eingetragen.")
    return redirect(url_for("challenge_activities.my_week"))


@challenge_activities_bp.route("/my-week", methods=["GET"])
@login_required
def my_week():
    participation = _active_participation()

    offset = 0
    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0

    monday, sunday = _get_week_bounds(offset)

    # Fetch activities for this week (only from the user's active challenge if available)
    query = db.select(Activity).where(
        Activity.user_id == current_user.id,
        Activity.activity_date >= monday,
        Activity.activity_date <= sunday,
    )
    if participation:
        query = query.where(Activity.challenge_id == participation.challenge_id)

    activities = db.session.execute(query.order_by(Activity.activity_date)).scalars().all()

    # Build per-day structure
    days = []
    for i in range(7):
        day_date = monday + timedelta(days=i)
        day_activities = [a for a in activities if a.activity_date == day_date]
        total_minutes = sum(a.duration_minutes for a in day_activities)
        days.append(
            {
                "date": day_date,
                "activities": day_activities,
                "total_minutes": total_minutes,
                "short": total_minutes < 30 and total_minutes > 0,
                "missing": total_minutes == 0,
                "remaining": max(0, 30 - total_minutes),
            }
        )

    # Fulfilled days: days with at least 30 minutes
    fulfilled_days = sum(1 for d in days if d["total_minutes"] >= 30)
    weekly_goal = participation.weekly_goal if participation else 3

    has_connector = (
        ConnectorCredential.query.filter_by(user_id=current_user.id).first() is not None
    )

    return render_template(
        "activities/my_week.html",
        days=days,
        monday=monday,
        sunday=sunday,
        offset=offset,
        fulfilled_days=fulfilled_days,
        weekly_goal=weekly_goal,
        participation=participation,
        has_connector=has_connector,
    )


@challenge_activities_bp.route("/import", methods=["GET"])
@login_required
def import_form():
    participation = _active_participation()
    if participation is None:
        flash("Du nimmst aktuell an keiner Challenge teil.")
        return redirect(url_for("challenges.index"))

    # Find user's connector credentials
    credentials = ConnectorCredential.query.filter_by(user_id=current_user.id).all()
    if not credentials:
        flash("Verbinde zuerst einen Connector.", "info")
        return redirect(url_for("connectors.index"))

    offset = 0
    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0

    monday, sunday = _get_week_bounds(offset)

    # Use first available credential
    cred = credentials[0]
    provider_type = cred.provider_type

    connector_cls = PROVIDER_REGISTRY.get(provider_type)
    connector_activities = []
    error = None

    if connector_cls:
        connector = connector_cls(user_id=current_user.id)
        try:
            connector.connect(cred.credentials)
            updates = connector.get_token_updates()
            if updates:
                updated = dict(cred.credentials)
                updated.update(updates)
                cred.credentials = updated
                db.session.commit()
            raw = connector.get_activities(monday, sunday)

            # Build set of already-imported external_ids
            existing_ids = {
                a.external_id
                for a in db.session.execute(
                    db.select(Activity).where(
                        Activity.user_id == current_user.id,
                        Activity.external_id.isnot(None),
                    )
                ).scalars()
            }

            for idx, act in enumerate(raw):
                start_time = act.get("startTimeLocal", "")
                ext_id = f"{provider_type}:{start_time}"
                duration_sec = act.get("duration", 0)
                duration_min = max(1, int(duration_sec) // 60)
                distance_m = act.get("distance")
                connector_activities.append(
                    {
                        "idx": idx,
                        "external_id": ext_id,
                        "date": start_time[:10] if start_time else "",
                        "name": act.get("activityName", "–"),
                        "type": act.get("activityType", {}).get("typeKey", "–"),
                        "duration_min": duration_min,
                        "distance": f"{distance_m / 1000:.2f} km" if distance_m else "–",
                        "already_imported": ext_id in existing_ids,
                    }
                )
        except Exception:
            from flask import current_app
            current_app.logger.exception(
                "Import-Vorschau fehlgeschlagen provider=%s user=%s", provider_type, current_user.id
            )
            error = "Aktivitäten konnten nicht geladen werden. Bitte versuche es später erneut."

    return render_template(
        "activities/import.html",
        activities=connector_activities,
        provider_type=provider_type,
        monday=monday,
        sunday=sunday,
        offset=offset,
        participation=participation,
        error=error,
    )


@challenge_activities_bp.route("/import", methods=["POST"])
@login_required
def import_submit():
    participation = _active_participation()
    if participation is None:
        flash("Du nimmst aktuell an keiner Challenge teil.")
        return redirect(url_for("challenges.index"))

    credentials = ConnectorCredential.query.filter_by(user_id=current_user.id).all()
    if not credentials:
        flash("Verbinde zuerst einen Connector.", "info")
        return redirect(url_for("connectors.index"))

    offset = 0
    try:
        offset = int(request.form.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0

    monday, sunday = _get_week_bounds(offset)

    cred = credentials[0]
    provider_type = cred.provider_type

    connector_cls = PROVIDER_REGISTRY.get(provider_type)
    if not connector_cls:
        flash("Unbekannter Connector.", "danger")
        return redirect(url_for("challenge_activities.import_form"))

    connector = connector_cls(user_id=current_user.id)
    try:
        connector.connect(cred.credentials)
        updates = connector.get_token_updates()
        if updates:
            updated = dict(cred.credentials)
            updated.update(updates)
            cred.credentials = updated
            db.session.commit()
        raw = connector.get_activities(monday, sunday)
    except Exception:
        from flask import current_app
        current_app.logger.exception(
            "Import fehlgeschlagen provider=%s user=%s", provider_type, current_user.id
        )
        flash("Import fehlgeschlagen. Bitte versuche es später erneut.", "danger")
        return redirect(url_for("challenge_activities.import_form", offset=offset))

    selected_ext_ids = request.form.getlist("selected")
    if len(selected_ext_ids) > 200:
        flash("Maximal 200 Aktivitäten pro Import auswählbar.", "warning")
        return redirect(url_for("challenge_activities.import_form"))
    raw_by_ext_id = {
        f"{provider_type}:{a['startTimeLocal']}": a for a in raw
    }
    imported = 0
    for ext_id in selected_ext_ids:
        act = raw_by_ext_id.get(ext_id)
        if act is None:
            continue  # Aktivität nicht mehr in der Liste
        # Periodenprüfung
        activity_date = date.fromisoformat(act["startTimeLocal"][:10])
        challenge = db.session.get(Challenge, participation.challenge_id)
        if not (challenge.start_date <= activity_date <= challenge.end_date):
            continue  # Aktivität liegt außerhalb der Challenge-Periode
        try:
            activity = Activity(
                user_id=current_user.id,
                challenge_id=participation.challenge_id,
                activity_date=activity_date,
                duration_minutes=max(1, int(act["duration"]) // 60),
                sport_type=act.get("activityType", {}).get("typeKey", "unknown"),
                source=provider_type,
                external_id=ext_id,
            )
            db.session.add(activity)
            db.session.commit()
            imported += 1
        except IntegrityError:
            db.session.rollback()
            # Duplikat – bereits importiert, kein Fehler anzeigen

    flash(f"{imported} Aktivität(en) erfolgreich importiert.")
    return redirect(url_for("challenge_activities.my_week"))


@challenge_activities_bp.route("/<int:activity_id>/delete", methods=["POST"])
@login_required
def delete_activity(activity_id):
    activity = db.session.get(Activity, activity_id)
    if activity is None or activity.user_id != current_user.id:
        flash("Aktivität nicht gefunden oder keine Berechtigung.")
        return redirect(url_for("challenge_activities.my_week"))

    delete_media_files(activity.media)
    if activity.screenshot_path:        # Legacy-Cleanup
        delete_upload(activity.screenshot_path)

    db.session.delete(activity)
    db.session.commit()

    flash("Aktivität wurde gelöscht.")
    return redirect(url_for("challenge_activities.my_week"))


@challenge_activities_bp.route("/<int:activity_id>", methods=["GET"])
@login_required
def activity_detail(activity_id):
    activity = db.session.get(Activity, activity_id)
    if activity is None:
        flash("Aktivität nicht gefunden.", "danger")
        return redirect(url_for("challenge_activities.my_week"))
    # Berechtigungscheck: Eigentümer ODER Challenge-Teilnehmer
    is_owner = activity.user_id == current_user.id
    participation = db.session.scalar(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.challenge_id == activity.challenge_id,
            ChallengeParticipation.status.in_(["accepted", "bailed_out"]),
        )
    )
    if not is_owner and participation is None:
        flash("Keine Berechtigung für diese Aktivität.", "danger")
        return redirect(url_for("challenge_activities.my_week"))
    challenge = db.session.get(Challenge, activity.challenge_id)
    owner = db.session.get(User, activity.user_id)
    return render_template(
        "activities/detail.html",
        activity=activity,
        challenge=challenge,
        owner=owner,
        is_owner=is_owner,
    )


@challenge_activities_bp.route("/user/<int:user_id>", methods=["GET"])
@login_required
def user_activities(user_id):
    target_user = db.session.get(User, user_id)
    if target_user is None:
        flash("Benutzer nicht gefunden.", "danger")
        return redirect(url_for("dashboard.index"))
    # Aktive Challenge des aktuellen Users
    my_participation = _active_participation()
    if my_participation is None:
        flash("Du nimmst an keiner aktiven Challenge teil.", "warning")
        return redirect(url_for("dashboard.index"))
    challenge = db.session.get(Challenge, my_participation.challenge_id)
    # Ziel-User muss dieselbe Challenge haben
    target_participation = db.session.scalar(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == user_id,
            ChallengeParticipation.challenge_id == challenge.id,
        )
    )
    if target_participation is None:
        flash("Dieser Benutzer nimmt nicht an deiner Challenge teil.", "warning")
        return redirect(url_for("dashboard.index"))
    activities = db.session.scalars(
        db.select(Activity)
        .where(
            Activity.user_id == user_id,
            Activity.challenge_id == challenge.id,
        )
        .order_by(Activity.activity_date.desc(), Activity.created_at.desc())
    ).all()
    return render_template(
        "activities/user_activities.html",
        target_user=target_user,
        target_participation=target_participation,
        challenge=challenge,
        activities=activities,
    )


@challenge_activities_bp.route("/<int:activity_id>/media/add", methods=["GET", "POST"])
@login_required
def add_media(activity_id: int):
    activity = db.session.get(Activity, activity_id)
    if activity is None or activity.user_id != current_user.id:
        flash("Keine Berechtigung.", "danger")
        return redirect(url_for("challenge_activities.my_week"))
    if request.method == "POST":
        media_files = request.files.getlist("media")
        any_saved = False
        for f in media_files:
            if f and f.filename:
                path = save_upload(f)
                if path is None:
                    flash("Ungültiges Dateiformat (erlaubt: JPG, PNG, WebP, MP4, MOV, WebM, max. 50 MB).", "danger")
                    return redirect(request.url)
                db.session.add(ActivityMedia(
                    activity_id=activity.id,
                    file_path=path,
                    media_type=get_media_type(f.filename),
                    original_filename=f.filename,
                    file_size_bytes=0,
                ))
                any_saved = True
        if any_saved:
            db.session.commit()
            flash("Medien erfolgreich hinzugefügt.", "success")
        return redirect(url_for("challenge_activities.activity_detail", activity_id=activity_id))
    return render_template("activities/add_media.html", activity=activity)


@challenge_activities_bp.route(
    "/<int:activity_id>/media/<int:media_id>/delete", methods=["POST"]
)
@login_required
def delete_media(activity_id: int, media_id: int):
    activity = db.session.get(Activity, activity_id)
    if activity is None or activity.user_id != current_user.id:
        flash("Keine Berechtigung.", "danger")
        return redirect(url_for("challenge_activities.my_week"))

    media = db.session.get(ActivityMedia, media_id)
    if media is None or media.activity_id != activity_id:
        flash("Medium nicht gefunden.", "warning")
        return redirect(
            url_for("challenge_activities.activity_detail", activity_id=activity_id)
        )

    delete_upload(media.file_path)
    db.session.delete(media)
    db.session.commit()

    flash("Medium wurde gelöscht.")
    return redirect(
        url_for("challenge_activities.activity_detail", activity_id=activity_id)
    )
