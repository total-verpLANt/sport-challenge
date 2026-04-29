from datetime import date, timedelta

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.extensions import db, limiter
from app.models.activity import Activity, ActivityLike
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.user import User
from app.services.weekly_summary import get_challenge_summary
from app.utils.motivational_quotes import get_random_quote

dashboard_bp = Blueprint("dashboard", __name__, template_folder="../templates")


@dashboard_bp.route("/")
@login_required
def index():
    today = date.today()

    # Find active challenge: today is between start and end date
    challenge = db.session.execute(
        db.select(Challenge)
        .where(
            Challenge.start_date <= today,
            Challenge.end_date >= today,
        )
        .order_by(Challenge.created_at.desc())
    ).scalars().first()

    # Fallback: most recent challenge if no active one
    if challenge is None:
        challenge = db.session.execute(
            db.select(Challenge).order_by(Challenge.created_at.desc())
        ).scalars().first()

    if challenge is None:
        return render_template(
            "dashboard/index.html",
            summary=None,
            timedelta=timedelta,
            feed_activities=[],
            feed_quotes={},
            liked_ids={},
            challenge=None,
        )

    summary = get_challenge_summary(challenge)

    # Alle Teilnehmer-IDs der aktuellen Challenge (accepted + bailed_out)
    participant_ids = db.session.scalars(
        db.select(ChallengeParticipation.user_id).where(
            ChallengeParticipation.challenge_id == challenge.id,
            ChallengeParticipation.status.in_(["accepted", "bailed_out"]),
        )
    ).all()

    # Activity-Feed: 10 neuste Activities
    feed_activities = db.session.scalars(
        db.select(Activity)
        .where(
            Activity.challenge_id == challenge.id,
            Activity.user_id.in_(participant_ids),
        )
        .order_by(Activity.activity_date.desc(), func.coalesce(Activity.started_at, Activity.created_at).desc())
        .limit(10)
        .options(selectinload(Activity.media), selectinload(Activity.likes))
    ).all()

    # Motivationssprüche pro Activity
    feed_quotes = {a.id: get_random_quote() for a in feed_activities}

    # Like-Status des aktuellen Users pro Activity
    liked_ids = {
        a.id: {like.user_id for like in a.likes}
        for a in feed_activities
    }

    # Display-Namen pro Activity (User-Lookup via participant_ids)
    user_ids = {a.user_id for a in feed_activities}
    users = db.session.scalars(db.select(User).where(User.id.in_(user_ids))).all()
    feed_user_names = {u.id: u.display_name for u in users}

    return render_template(
        "dashboard/index.html",
        summary=summary,
        timedelta=timedelta,
        feed_activities=feed_activities,
        feed_quotes=feed_quotes,
        liked_ids=liked_ids,
        feed_user_names=feed_user_names,
        challenge=challenge,
    )


@dashboard_bp.route("/leaderboard")
@login_required
def leaderboard():
    today = date.today()
    challenge = db.session.execute(
        db.select(Challenge)
        .where(Challenge.start_date <= today, Challenge.end_date >= today)
        .order_by(Challenge.created_at.desc())
    ).scalars().first()
    if challenge is None:
        challenge = db.session.execute(
            db.select(Challenge).order_by(Challenge.created_at.desc())
        ).scalars().first()
    if challenge is None:
        return render_template("dashboard/leaderboard.html", summary=None, timedelta=timedelta)
    summary = get_challenge_summary(challenge)
    return render_template("dashboard/leaderboard.html", summary=summary, timedelta=timedelta)


@dashboard_bp.route("/feed")
@login_required
def feed():
    """AJAX-Endpunkt für paginiertes Nachladen des Activity-Feeds."""
    challenge_id = request.args.get("challenge_id", type=int)
    page = max(0, request.args.get("page", 0, type=int))

    if not challenge_id:
        return jsonify({"activities": [], "has_more": False})

    # Berechtigung: current_user muss Teilnehmer sein
    participation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.challenge_id == challenge_id,
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.status.in_(["accepted", "bailed_out"]),
        )
    ).scalars().first()

    if not participation:
        return jsonify({"activities": [], "has_more": False}), 403

    participant_ids = db.session.scalars(
        db.select(ChallengeParticipation.user_id).where(
            ChallengeParticipation.challenge_id == challenge_id,
            ChallengeParticipation.status.in_(["accepted", "bailed_out"]),
        )
    ).all()

    offset = page * 10
    activities = db.session.scalars(
        db.select(Activity)
        .where(
            Activity.challenge_id == challenge_id,
            Activity.user_id.in_(participant_ids),
        )
        .order_by(Activity.activity_date.desc(), func.coalesce(Activity.started_at, Activity.created_at).desc())
        .offset(offset)
        .limit(11)  # 11 laden um has_more zu prüfen
        .options(selectinload(Activity.media), selectinload(Activity.likes))
    ).all()

    has_more = len(activities) > 10
    activities = activities[:10]

    # User-Objekte laden
    user_map = {}
    for a in activities:
        if a.user_id not in user_map:
            user_map[a.user_id] = db.session.get(User, a.user_id)

    result = []
    for a in activities:
        user = user_map.get(a.user_id)
        result.append({
            "id": a.id,
            "user_display_name": user.display_name if user else "Unbekannt",
            "activity_date": a.activity_date.strftime("%d.%m.%Y"),
            "created_at_time": (a.started_at or a.created_at).strftime("%H:%M"),
            "sport_type": a.sport_type,
            "duration_minutes": a.duration_minutes,
            "notes": a.notes or "",
            "quote": get_random_quote(),
            "liked_by_me": current_user.id in {like.user_id for like in a.likes},
            "like_count": len(a.likes),
            "media": [
                {
                    "file_path": m.file_path,
                    "media_type": m.media_type,
                    "original_filename": m.original_filename,
                }
                for m in a.media
            ],
        })

    return jsonify({"activities": result, "has_more": has_more})


@dashboard_bp.route("/activities/<int:activity_id>/like", methods=["POST"])
@login_required
@limiter.limit("30/minute")
def like_activity(activity_id: int):
    """AJAX-Like-Toggle: Like hinzufügen oder entfernen."""
    activity = db.session.get(Activity, activity_id)
    if not activity:
        return jsonify({"error": "nicht gefunden"}), 404

    # Berechtigung: current_user muss Teilnehmer derselben Challenge sein
    participation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.challenge_id == activity.challenge_id,
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.status.in_(["accepted", "bailed_out"]),
        )
    ).scalars().first()

    if not participation:
        return jsonify({"error": "keine Berechtigung"}), 403

    existing_like = db.session.execute(
        db.select(ActivityLike).where(
            ActivityLike.activity_id == activity_id,
            ActivityLike.user_id == current_user.id,
        )
    ).scalars().first()

    if existing_like:
        db.session.delete(existing_like)
        db.session.commit()
        liked = False
    else:
        new_like = ActivityLike(activity_id=activity_id, user_id=current_user.id)
        db.session.add(new_like)
        db.session.commit()
        liked = True

    count = db.session.scalar(
        db.select(db.func.count(ActivityLike.id)).where(
            ActivityLike.activity_id == activity_id
        )
    )

    return jsonify({"liked": liked, "count": count})
