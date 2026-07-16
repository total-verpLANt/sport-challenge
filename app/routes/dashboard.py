import uuid as _uuid
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, abort, jsonify, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.extensions import db, limiter
from app.models.activity import Activity, ActivityComment, ActivityLike
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.donation import DonationProposal
from app.models.sick_period import SickPeriod, SickPeriodComment, SickPeriodLike
from app.models.user import User
from app.routes.donation import _get_poll, _user_is_participant
from app.services import notifications as notif_service
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


def _comment_to_dict(c, delete_endpoint: str, current_user_id: int, is_admin: bool) -> dict:
    return {
        "id": c.id,
        "body": c.body,
        "user_display_name": c.user.display_name if c.user else "Unbekannt",
        "time": c.created_at.strftime("%d.%m.%Y %H:%M"),
        "delete_url": url_for(delete_endpoint, comment_id=c.id),
        "can_delete": c.user_id == current_user_id or is_admin,
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
        "comment_count": len(a.comments),
        "comments_url": url_for("dashboard.list_activity_comments", activity_id=a.id),
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
        "comment_count": len(p.comments),
        "comments_url": url_for("dashboard.list_sick_period_comments", sick_period_id=p.id),
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
            selectinload(Activity.comments),
        )
    ).all()

    periods = db.session.scalars(
        db.select(SickPeriod)
        .order_by(SickPeriod.created_at.desc())
        .limit(fetch_n)
        .options(
            selectinload(SickPeriod.likes).selectinload(SickPeriodLike.user),
            selectinload(SickPeriod.comments),
        )
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


def _poll_info(challenge: Challenge) -> dict:
    """Poll-Anreicherung eines Boards (Epic 1t8s.5).

    Liefert den DonationPoll der Challenge (oder None), den Gewinner-Vorschlag
    (nur wenn gesetzt) und ob current_user Teilnehmer ist (accepted/bailed_out).
    Einzel-Queries pro Board sind ok – es gibt max. eine Handvoll Boards.
    """
    poll = _get_poll(challenge.id)
    winner_proposal = None
    if poll is not None and poll.winner_proposal_id is not None:
        winner_proposal = db.session.get(DonationProposal, poll.winner_proposal_id)
    return {
        "poll": poll,
        "winner_proposal": winner_proposal,
        "is_participant": _user_is_participant(challenge.id),
    }


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
            {"kind": "active", "summary": get_challenge_summary(c), **_poll_info(c)}
            for c in active
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
        {"kind": "finished", "summary": get_challenge_summary(c), **_poll_info(c)}
        for c in finished
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

    feed_link = url_for("dashboard.index") + f"#feed-post-activity-{activity.id}"
    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        db.session.add(ActivityLike(activity_id=activity_id, user_id=current_user.id))
        liked = True
    db.session.flush()

    likes = db.session.scalars(
        db.select(ActivityLike)
        .where(ActivityLike.activity_id == activity_id)
        .options(selectinload(ActivityLike.user))
        .order_by(ActivityLike.id.desc())
    ).all()

    # Gebündelte Like-Notification: fremde Liker (ohne Urheber), neueste zuerst.
    foreign = [lk for lk in likes if lk.user_id != activity.user_id]
    notif_service.upsert_like_notification(
        activity.user_id,
        feed_link,
        [lk.user.display_name for lk in foreign],
        foreign[0].user_id if foreign else None,
    )
    db.session.commit()

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

    feed_link = url_for("dashboard.index") + f"#feed-post-absence-{period.id}"
    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        db.session.add(SickPeriodLike(sick_period_id=sick_period_id, user_id=current_user.id))
        liked = True
    db.session.flush()

    likes = db.session.scalars(
        db.select(SickPeriodLike)
        .where(SickPeriodLike.sick_period_id == sick_period_id)
        .options(selectinload(SickPeriodLike.user))
        .order_by(SickPeriodLike.id.desc())
    ).all()

    # Gebündelte Like-Notification: fremde Liker (ohne Urheber), neueste zuerst.
    foreign = [lk for lk in likes if lk.user_id != period.user_id]
    notif_service.upsert_like_notification(
        period.user_id,
        feed_link,
        [lk.user.display_name for lk in foreign],
        foreign[0].user_id if foreign else None,
    )
    db.session.commit()

    liked_by = [like.user.display_name for like in likes]
    return jsonify({"liked": liked, "count": len(likes), "liked_by": liked_by})


@dashboard_bp.route("/activities/<int:activity_id>/comments", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def create_activity_comment(activity_id: int):
    """Kommentar an einer Aktivität anlegen (AJAX)."""
    activity = db.session.get(Activity, activity_id)
    if not activity:
        return jsonify({"error": "nicht gefunden"}), 404
    body = (request.form.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Kommentar darf nicht leer sein"}), 400
    if len(body) > 1000:
        return jsonify({"error": "Kommentar zu lang (max. 1000 Zeichen)"}), 400

    comment = ActivityComment(activity_id=activity_id, user_id=current_user.id, body=body)
    db.session.add(comment)
    db.session.flush()

    feed_link = url_for("dashboard.index") + f"#feed-post-activity-{activity.id}"
    all_comments = db.session.scalars(
        db.select(ActivityComment)
        .where(ActivityComment.activity_id == activity_id)
        .options(selectinload(ActivityComment.user))
        .order_by(ActivityComment.id.desc())
    ).all()

    # Gebündelte Kommentar-Notification: fremde Kommentatoren (ohne Autor), neueste zuerst.
    seen, foreign_names, latest_actor = set(), [], None
    for c in all_comments:
        if c.user_id == activity.user_id:
            continue
        if latest_actor is None:
            latest_actor = c.user_id
        if c.user_id not in seen:
            seen.add(c.user_id)
            foreign_names.append(c.user.display_name)
    notif_service.upsert_comment_notification(activity.user_id, feed_link, foreign_names, latest_actor)
    db.session.commit()

    return jsonify({
        "count": len(all_comments),
        "comment": _comment_to_dict(
            comment, "dashboard.delete_activity_comment", current_user.id, current_user.is_admin
        ),
    })


@dashboard_bp.route("/activities/<int:activity_id>/comments", methods=["GET"])
@login_required
def list_activity_comments(activity_id: int):
    """Kommentare einer Aktivität nachladen (AJAX, Lazy-Load)."""
    activity = db.session.get(Activity, activity_id)
    if not activity:
        return jsonify({"error": "nicht gefunden"}), 404

    comments = db.session.scalars(
        db.select(ActivityComment)
        .where(ActivityComment.activity_id == activity_id)
        .options(selectinload(ActivityComment.user))
        .order_by(ActivityComment.id.asc())
    ).all()
    return jsonify({
        "comments": [
            _comment_to_dict(
                c, "dashboard.delete_activity_comment", current_user.id, current_user.is_admin
            )
            for c in comments
        ]
    })


@dashboard_bp.route("/activity-comments/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_activity_comment(comment_id: int):
    """Eigenen Kommentar (oder als Admin fremden) an einer Aktivität löschen."""
    comment = db.session.get(ActivityComment, comment_id)
    if not comment:
        return jsonify({"error": "nicht gefunden"}), 404
    if comment.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "nicht erlaubt"}), 403

    activity = db.session.get(Activity, comment.activity_id)
    db.session.delete(comment)
    db.session.flush()

    remaining = db.session.scalars(
        db.select(ActivityComment)
        .where(ActivityComment.activity_id == comment.activity_id)
        .options(selectinload(ActivityComment.user))
        .order_by(ActivityComment.id.desc())
    ).all()

    if activity is not None:
        feed_link = url_for("dashboard.index") + f"#feed-post-activity-{activity.id}"
        seen, foreign_names, latest_actor = set(), [], None
        for c in remaining:
            if c.user_id == activity.user_id:
                continue
            if latest_actor is None:
                latest_actor = c.user_id
            if c.user_id not in seen:
                seen.add(c.user_id)
                foreign_names.append(c.user.display_name)
        notif_service.upsert_comment_notification(activity.user_id, feed_link, foreign_names, latest_actor)

    db.session.commit()
    return jsonify({"count": len(remaining)})


@dashboard_bp.route("/sick-periods/<int:sick_period_id>/comments", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def create_sick_period_comment(sick_period_id: int):
    """Kommentar an einer Abwesenheit anlegen (AJAX)."""
    period = db.session.get(SickPeriod, sick_period_id)
    if not period:
        return jsonify({"error": "nicht gefunden"}), 404
    body = (request.form.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Kommentar darf nicht leer sein"}), 400
    if len(body) > 1000:
        return jsonify({"error": "Kommentar zu lang (max. 1000 Zeichen)"}), 400

    comment = SickPeriodComment(sick_period_id=sick_period_id, user_id=current_user.id, body=body)
    db.session.add(comment)
    db.session.flush()

    feed_link = url_for("dashboard.index") + f"#feed-post-absence-{period.id}"
    all_comments = db.session.scalars(
        db.select(SickPeriodComment)
        .where(SickPeriodComment.sick_period_id == sick_period_id)
        .options(selectinload(SickPeriodComment.user))
        .order_by(SickPeriodComment.id.desc())
    ).all()

    # Gebündelte Kommentar-Notification: fremde Kommentatoren (ohne Autor), neueste zuerst.
    seen, foreign_names, latest_actor = set(), [], None
    for c in all_comments:
        if c.user_id == period.user_id:
            continue
        if latest_actor is None:
            latest_actor = c.user_id
        if c.user_id not in seen:
            seen.add(c.user_id)
            foreign_names.append(c.user.display_name)
    notif_service.upsert_comment_notification(period.user_id, feed_link, foreign_names, latest_actor)
    db.session.commit()

    return jsonify({
        "count": len(all_comments),
        "comment": _comment_to_dict(
            comment, "dashboard.delete_sick_period_comment", current_user.id, current_user.is_admin
        ),
    })


@dashboard_bp.route("/sick-periods/<int:sick_period_id>/comments", methods=["GET"])
@login_required
def list_sick_period_comments(sick_period_id: int):
    """Kommentare einer Abwesenheit nachladen (AJAX, Lazy-Load)."""
    period = db.session.get(SickPeriod, sick_period_id)
    if not period:
        return jsonify({"error": "nicht gefunden"}), 404

    comments = db.session.scalars(
        db.select(SickPeriodComment)
        .where(SickPeriodComment.sick_period_id == sick_period_id)
        .options(selectinload(SickPeriodComment.user))
        .order_by(SickPeriodComment.id.asc())
    ).all()
    return jsonify({
        "comments": [
            _comment_to_dict(
                c, "dashboard.delete_sick_period_comment", current_user.id, current_user.is_admin
            )
            for c in comments
        ]
    })


@dashboard_bp.route("/sick-period-comments/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_sick_period_comment(comment_id: int):
    """Eigenen Kommentar (oder als Admin fremden) an einer Abwesenheit löschen."""
    comment = db.session.get(SickPeriodComment, comment_id)
    if not comment:
        return jsonify({"error": "nicht gefunden"}), 404
    if comment.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "nicht erlaubt"}), 403

    period = db.session.get(SickPeriod, comment.sick_period_id)
    db.session.delete(comment)
    db.session.flush()

    remaining = db.session.scalars(
        db.select(SickPeriodComment)
        .where(SickPeriodComment.sick_period_id == comment.sick_period_id)
        .options(selectinload(SickPeriodComment.user))
        .order_by(SickPeriodComment.id.desc())
    ).all()

    if period is not None:
        feed_link = url_for("dashboard.index") + f"#feed-post-absence-{period.id}"
        seen, foreign_names, latest_actor = set(), [], None
        for c in remaining:
            if c.user_id == period.user_id:
                continue
            if latest_actor is None:
                latest_actor = c.user_id
            if c.user_id not in seen:
                seen.add(c.user_id)
                foreign_names.append(c.user.display_name)
        notif_service.upsert_comment_notification(period.user_id, feed_link, foreign_names, latest_actor)

    db.session.commit()
    return jsonify({"count": len(remaining)})
