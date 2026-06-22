import uuid as _uuid
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, abort, jsonify, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.extensions import db, limiter
from app.models.activity import Activity, ActivityLike
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.sick_period import SickPeriod, SickPeriodLike
from app.models.user import User
from app.services import notifications as notif_service
from app.services.notifications import NotificationType
from app.services.statistics import get_challenge_statistics
from app.services.weekly_summary import get_challenge_summary
from app.utils.motivational_quotes import get_random_quote

dashboard_bp = Blueprint("dashboard", __name__, template_folder="../templates")

FEED_PAGE_SIZE = 10

# Wie lange eine beendete Challenge als Abschluss-Karte oben sichtbar bleibt.
RECENT_FINISHED_DAYS = 14


def _get_challenge_by_public_id(public_id: str) -> Challenge:
    """Resolve a challenge by its public UUID or abort 404.

    No visibility gate: every logged-in user may view every leaderboard
    (login_required + is_approved still enforced upstream).
    """
    try:
        uid = _uuid.UUID(public_id)
    except (ValueError, AttributeError):
        abort(404)
    challenge = db.session.execute(
        db.select(Challenge).where(Challenge.public_id == uid)
    ).scalar_one_or_none()
    if challenge is None:
        abort(404)
    return challenge


def _feed_sort_key(dt: datetime) -> datetime:
    """Vergleichbarer Sortierschlüssel: naive datetimes als UTC interpretieren."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _challenge_label(challenges: dict, challenge_id: int) -> dict:
    """Challenge-Label-Felder (Name + Leaderboard-Link) für ein Feed-Item."""
    c = challenges.get(challenge_id)
    if c is None:
        return {"challenge_name": "", "challenge_url": None}
    return {
        "challenge_name": c.name,
        "challenge_url": url_for(
            "dashboard.leaderboard_challenge", public_id=str(c.public_id)
        ),
    }


def _activity_to_dict(a: Activity, users: dict, challenges: dict, current_user_id: int) -> dict:
    u = users.get(a.user_id)
    return {
        "type": "activity",
        "id": a.id,
        "user_display_name": u.display_name if u else "Unbekannt",
        "activity_date": a.activity_date.strftime("%d.%m.%Y"),
        "time": (a.started_at or a.created_at).strftime("%H:%M"),
        "sport_type": a.sport_type,
        "duration_minutes": a.duration_minutes,
        "notes": a.notes or "",
        "quote": get_random_quote(),
        "like_url": url_for("dashboard.like_activity", activity_id=a.id),
        "liked_by_me": current_user_id in {like.user_id for like in a.likes},
        "like_count": len(a.likes),
        "liked_by": [like.user.display_name for like in a.likes if like.user],
        "media": [
            {
                "url": url_for("media.activity_media", media_id=m.id),
                "media_type": m.media_type,
                "original_filename": m.original_filename,
            }
            for m in a.media
        ],
        **_challenge_label(challenges, a.challenge_id),
    }


def _absence_to_dict(p: SickPeriod, users: dict, challenges: dict, current_user_id: int) -> dict:
    u = users.get(p.user_id)
    return {
        "type": "absence",
        "id": p.id,
        "user_display_name": u.display_name if u else "Unbekannt",
        "start_date": p.start_date.strftime("%d.%m.%Y"),
        "end_date": p.end_date.strftime("%d.%m.%Y"),
        "reason": p.reason or "",
        "like_url": url_for("dashboard.like_sick_period", sick_period_id=p.id),
        "liked_by_me": current_user_id in {like.user_id for like in p.likes},
        "like_count": len(p.likes),
        "liked_by": [like.user.display_name for like in p.likes if like.user],
        **_challenge_label(challenges, p.challenge_id),
    }


def _build_feed_items(current_user_id: int, page: int):
    """Globaler Feed (Aktivitäten + Abwesenheiten ALLER Challenges).

    Beide Quellen werden bis (page+1)*PAGE_SIZE+1 geladen, in Python gemerged,
    nach Zeitstempel sortiert und dann auf die Seite zugeschnitten. Kein
    Challenge-/Teilnahme-Filter: jeder eingeloggte Nutzer sieht alles. User- und
    Challenge-Namen werden per Bulk-Load aufgelöst (kein N+1).
    """
    fetch_n = (page + 1) * FEED_PAGE_SIZE + 1

    activities = db.session.scalars(
        db.select(Activity)
        .order_by(func.coalesce(Activity.started_at, Activity.created_at).desc())
        .limit(fetch_n)
        .options(
            selectinload(Activity.media),
            selectinload(Activity.likes).selectinload(ActivityLike.user),
        )
    ).all()

    periods = db.session.scalars(
        db.select(SickPeriod)
        .order_by(SickPeriod.created_at.desc())
        .limit(fetch_n)
        .options(selectinload(SickPeriod.likes).selectinload(SickPeriodLike.user))
    ).all()

    uid_set = {a.user_id for a in activities} | {p.user_id for p in periods}
    users = (
        {u.id: u for u in db.session.scalars(db.select(User).where(User.id.in_(uid_set))).all()}
        if uid_set
        else {}
    )

    cid_set = {a.challenge_id for a in activities} | {p.challenge_id for p in periods}
    challenges = (
        {
            c.id: c
            for c in db.session.scalars(
                db.select(Challenge).where(Challenge.id.in_(cid_set))
            ).all()
        }
        if cid_set
        else {}
    )

    items = []
    for a in activities:
        items.append((_feed_sort_key(a.started_at or a.created_at),
                      _activity_to_dict(a, users, challenges, current_user_id)))
    for p in periods:
        items.append((_feed_sort_key(p.created_at),
                      _absence_to_dict(p, users, challenges, current_user_id)))

    items.sort(key=lambda t: t[0], reverse=True)

    start = page * FEED_PAGE_SIZE
    end = start + FEED_PAGE_SIZE
    has_more = len(items) > end
    return [d for _, d in items[start:end]], has_more


def _build_dashboard_boards(today: date) -> list[dict]:
    """Baut die Liste der Dashboard-Boards (Top-Bereich).

    - Jede AKTIVE Challenge (start <= today <= end) → Top-5-Board mit
      Spendentopf.
    - Sonst (keine aktive): kürzlich beendete Challenges (end < today und
      end >= today - RECENT_FINISHED_DAYS) → Abschluss-Karte mit finaler
      Spendensumme + Leaderboard-Link.
    - Greift nichts, wird die neueste Challenge als Abschluss-Karte gezeigt,
      damit das Dashboard nie leer ist.
    """
    active = db.session.scalars(
        db.select(Challenge)
        .where(Challenge.start_date <= today, Challenge.end_date >= today)
        .order_by(Challenge.created_at.desc())
    ).all()

    if active:
        return [
            {"kind": "active", "summary": get_challenge_summary(c)} for c in active
        ]

    # Keine aktive Challenge → kürzlich beendete als Abschluss-Karten
    cutoff = today - timedelta(days=RECENT_FINISHED_DAYS)
    finished = db.session.scalars(
        db.select(Challenge)
        .where(Challenge.end_date < today, Challenge.end_date >= cutoff)
        .order_by(Challenge.end_date.desc())
    ).all()

    if not finished:
        # Fallback: neueste Challenge überhaupt, damit das Dashboard nie leer ist
        newest = db.session.scalars(
            db.select(Challenge).order_by(Challenge.created_at.desc()).limit(1)
        ).first()
        finished = [newest] if newest else []

    return [
        {"kind": "finished", "summary": get_challenge_summary(c)} for c in finished
    ]


@dashboard_bp.route("/")
@login_required
def index():
    today = date.today()

    boards = _build_dashboard_boards(today)

    # Offene Challenge-Einladungen des Users → prominente Karte oben im Dashboard.
    # Bewusst Plural-fähig (alle 'invited'): ein User kann zu mehreren Challenges
    # gleichzeitig eingeladen sein. Challenge wird eager geladen (kein N+1).
    pending_invitations = db.session.scalars(
        db.select(ChallengeParticipation)
        .where(
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.status == "invited",
        )
        .options(selectinload(ChallengeParticipation.challenge))
        .order_by(ChallengeParticipation.invited_at.desc())
    ).all()

    # Globaler Feed über ALLE Challenges (alle sehen alles)
    feed_items, feed_has_more = _build_feed_items(current_user.id, page=0)

    return render_template(
        "dashboard/index.html",
        boards=boards,
        pending_invitations=pending_invitations,
        timedelta=timedelta,
        feed_items=feed_items,
        feed_has_more=feed_has_more,
    )


@dashboard_bp.route("/leaderboard")
@login_required
def leaderboard():
    """Leaderboard der aktiven/neuesten Challenge (Fallback ohne public_id)."""
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
        return render_template(
            "dashboard/leaderboard.html", summary=None, stats=None, timedelta=timedelta
        )
    return _render_leaderboard(challenge)


@dashboard_bp.route("/leaderboard/<public_id>")
@login_required
def leaderboard_challenge(public_id: str):
    """Leaderboard einer bestimmten Challenge (alle sehen alles)."""
    challenge = _get_challenge_by_public_id(public_id)
    return _render_leaderboard(challenge)


def _render_leaderboard(challenge: Challenge):
    summary = get_challenge_summary(challenge)
    stats = get_challenge_statistics(challenge)
    return render_template(
        "dashboard/leaderboard.html", summary=summary, stats=stats, timedelta=timedelta
    )


@dashboard_bp.route("/feed")
@login_required
def feed():
    """AJAX-Endpunkt für paginiertes Nachladen des globalen Feeds.

    Kein challenge_id-/Teilnahme-Gate: jeder eingeloggte Nutzer sieht den
    Feed aller Challenges.
    """
    page = max(0, request.args.get("page", 0, type=int))
    items, has_more = _build_feed_items(current_user.id, page=page)
    return jsonify({"items": items, "has_more": has_more})


@dashboard_bp.route("/activities/<int:activity_id>/like", methods=["POST"])
@login_required
@limiter.limit("30/minute")
def like_activity(activity_id: int):
    """AJAX-Like-Toggle für eine Aktivität.

    Alle eingeloggten Nutzer dürfen jede Aktivität liken (kein
    Teilnahme-Gate) – konsistent zum offenen Lesemodell.
    """
    activity = db.session.get(Activity, activity_id)
    if not activity:
        return jsonify({"error": "nicht gefunden"}), 404

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
        db.session.add(ActivityLike(activity_id=activity_id, user_id=current_user.id))
        if activity.user_id != current_user.id:
            notif_service.create_notification(
                activity.user_id,
                NotificationType.ACTIVITY_LIKED,
                f"{current_user.display_name} hat deinen Beitrag geliked",
                link_url=url_for("dashboard.index") + f"#feed-post-activity-{activity.id}",
            )
        db.session.commit()
        liked = True

    likes = db.session.scalars(
        db.select(ActivityLike)
        .where(ActivityLike.activity_id == activity_id)
        .options(selectinload(ActivityLike.user))
    ).all()

    liked_by = [like.user.display_name for like in likes]
    return jsonify({"liked": liked, "count": len(likes), "liked_by": liked_by})


@dashboard_bp.route("/sick-periods/<int:sick_period_id>/like", methods=["POST"])
@login_required
@limiter.limit("30/minute")
def like_sick_period(sick_period_id: int):
    """AJAX-Like-Toggle für eine Abwesenheit.

    Alle eingeloggten Nutzer dürfen liken (kein Teilnahme-Gate).
    """
    period = db.session.get(SickPeriod, sick_period_id)
    if not period:
        return jsonify({"error": "nicht gefunden"}), 404

    existing_like = db.session.execute(
        db.select(SickPeriodLike).where(
            SickPeriodLike.sick_period_id == sick_period_id,
            SickPeriodLike.user_id == current_user.id,
        )
    ).scalars().first()

    if existing_like:
        db.session.delete(existing_like)
        db.session.commit()
        liked = False
    else:
        db.session.add(SickPeriodLike(sick_period_id=sick_period_id, user_id=current_user.id))
        if period.user_id != current_user.id:
            notif_service.create_notification(
                period.user_id,
                NotificationType.ACTIVITY_LIKED,
                f"{current_user.display_name} hat deinen Beitrag geliked",
                link_url=url_for("dashboard.index") + f"#feed-post-absence-{period.id}",
            )
        db.session.commit()
        liked = True

    likes = db.session.scalars(
        db.select(SickPeriodLike)
        .where(SickPeriodLike.sick_period_id == sick_period_id)
        .options(selectinload(SickPeriodLike.user))
    ).all()

    liked_by = [like.user.display_name for like in likes]
    return jsonify({"liked": liked, "count": len(likes), "liked_by": liked_by})
