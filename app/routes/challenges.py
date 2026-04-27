from datetime import date, datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.sick_week import SickWeek
from app.models.user import User
from app.utils.decorators import admin_required

challenges_bp = Blueprint("challenges", __name__, template_folder="../templates")


def _get_challenge_by_public_id(public_id: str) -> Challenge:
    challenge = db.session.execute(
        db.select(Challenge).where(Challenge.public_id == public_id)
    ).scalar_one_or_none()
    if challenge is None:
        abort(404)
    return challenge


@challenges_bp.route("/")
@login_required
def index():
    # Alle Challenge-IDs, an denen der User teilnimmt (alle Status)
    my_challenge_ids = db.session.scalars(
        db.select(ChallengeParticipation.challenge_id).where(
            ChallengeParticipation.user_id == current_user.id
        )
    ).all()

    # Alle für den User sichtbaren Challenges: eigene Participations ODER öffentliche
    visible_challenges = db.session.scalars(
        db.select(Challenge)
        .where(
            db.or_(
                Challenge.id.in_(my_challenge_ids),
                Challenge.is_public == True,  # noqa: E712
            )
        )
        .order_by(Challenge.created_at.desc())
    ).all()

    # Admins sehen zusätzlich alle privaten Challenges
    if current_user.is_admin:
        visible_challenges = db.session.scalars(
            db.select(Challenge).order_by(Challenge.created_at.desc())
        ).all()

    # Aktive Participation des Users (für schnellen Zugriff)
    active_participation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.status == "accepted",
        )
    ).scalar_one_or_none()

    # Ausstehende Einladung
    pending_invitation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.status == "invited",
        )
    ).scalar_one_or_none()

    # Teilnahme-Status-Map: challenge_id → participation (für Template-Kennzeichnung)
    participation_by_challenge = {
        p.challenge_id: p
        for p in db.session.scalars(
            db.select(ChallengeParticipation).where(
                ChallengeParticipation.user_id == current_user.id
            )
        ).all()
    }

    return render_template(
        "challenges/index.html",
        visible_challenges=visible_challenges,
        pending_invitation=pending_invitation,
        active_participation=active_participation,
        participation_by_challenge=participation_by_challenge,
    )


@challenges_bp.route("/create")
@admin_required
def create():
    return render_template("challenges/create.html")


@challenges_bp.route("/create", methods=["POST"])
@admin_required
def create_post():
    name = request.form.get("name", "").strip()
    start_date_str = request.form.get("start_date", "")
    end_date_str = request.form.get("end_date", "")
    penalty_per_miss = request.form.get("penalty_per_miss", "5")
    bailout_fee = request.form.get("bailout_fee", "25")
    is_public = request.form.get("is_public") == "1"

    errors = []
    if not name:
        errors.append("Name darf nicht leer sein.")

    start_date = None
    end_date = None
    try:
        start_date = date.fromisoformat(start_date_str)
    except ValueError:
        errors.append("Ungültiges Startdatum.")

    try:
        end_date = date.fromisoformat(end_date_str)
    except ValueError:
        errors.append("Ungültiges Enddatum.")

    if start_date and end_date:
        if start_date >= end_date:
            errors.append("Startdatum muss vor Enddatum liegen.")

    try:
        penalty_val = float(penalty_per_miss)
    except ValueError:
        penalty_val = 5.0
        errors.append("Ungültiger Wert für Strafe pro Versäumnis.")

    try:
        bailout_val = float(bailout_fee)
    except ValueError:
        bailout_val = 25.0
        errors.append("Ungültiger Wert für Bailout-Gebühr.")

    if errors:
        for error in errors:
            flash(error)
        return render_template(
            "challenges/create.html",
            form_data=request.form,
        )

    challenge = Challenge(
        name=name,
        start_date=start_date,
        end_date=end_date,
        penalty_per_miss=penalty_val,
        bailout_fee=bailout_val,
        is_public=is_public,
        created_by_id=current_user.id,
    )
    db.session.add(challenge)
    db.session.commit()

    flash(f"Challenge '{challenge.name}' wurde erfolgreich erstellt.")
    return redirect(url_for("challenges.detail", public_id=str(challenge.public_id)))


@challenges_bp.route("/<string:public_id>")
@login_required
def detail(public_id):
    challenge = _get_challenge_by_public_id(public_id)

    participations = db.session.scalars(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.challenge_id == challenge.id
        )
    ).all()

    my_participation = next(
        (p for p in participations if p.user_id == current_user.id), None
    )

    # Sichtbarkeitsprüfung: nicht-öffentliche Challenges nur für Teilnehmer/Admin
    if not challenge.is_public and not current_user.is_admin and my_participation is None:
        abort(403)

    uninvited_users = []
    if current_user.is_admin:
        participant_ids = {p.user_id for p in participations}
        all_approved_users = db.session.scalars(
            db.select(User).where(User.is_approved == True)  # noqa: E712
        ).all()
        uninvited_users = [u for u in all_approved_users if u.id not in participant_ids]

    return render_template(
        "challenges/detail.html",
        challenge=challenge,
        participations=participations,
        my_participation=my_participation,
        uninvited_users=uninvited_users,
    )


@challenges_bp.route("/<string:public_id>/invite", methods=["POST"])
@admin_required
def invite(public_id):
    challenge = _get_challenge_by_public_id(public_id)

    user_id = request.form.get("user_id", type=int)
    if not user_id:
        flash("Bitte einen Benutzer auswählen.")
        return redirect(url_for("challenges.detail", public_id=public_id))

    user = db.session.get(User, user_id)
    if user is None:
        flash("Benutzer nicht gefunden.")
        return redirect(url_for("challenges.detail", public_id=public_id))

    existing = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == user_id,
            ChallengeParticipation.challenge_id == challenge.id,
        )
    ).scalar_one_or_none()

    if existing:
        flash(f"{user.display_name} ist bereits in dieser Challenge.")
        return redirect(url_for("challenges.detail", public_id=public_id))

    participation = ChallengeParticipation(
        user_id=user_id,
        challenge_id=challenge.id,
        status="invited",
    )
    db.session.add(participation)
    db.session.commit()

    flash(f"{user.display_name} wurde zur Challenge eingeladen.")
    return redirect(url_for("challenges.detail", public_id=public_id))


@challenges_bp.route("/<string:public_id>/accept", methods=["POST"])
@login_required
def accept(public_id):
    challenge = _get_challenge_by_public_id(public_id)

    participation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.challenge_id == challenge.id,
            ChallengeParticipation.status == "invited",
        )
    ).scalar_one_or_none()

    if participation is None:
        flash("Keine ausstehende Einladung gefunden.")
        return redirect(url_for("challenges.detail", public_id=public_id))

    weekly_goal_str = request.form.get("weekly_goal", "3")
    try:
        weekly_goal = int(weekly_goal_str)
        if weekly_goal not in (2, 3):
            weekly_goal = 3
    except ValueError:
        weekly_goal = 3

    participation.status = "accepted"
    participation.accepted_at = datetime.now(timezone.utc)
    participation.weekly_goal = weekly_goal
    db.session.commit()

    flash("Du hast die Challenge-Einladung angenommen. Viel Erfolg!")
    return redirect(url_for("challenges.detail", public_id=public_id))


@challenges_bp.route("/<string:public_id>/decline", methods=["POST"])
@login_required
def decline(public_id):
    challenge = _get_challenge_by_public_id(public_id)

    participation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.challenge_id == challenge.id,
            ChallengeParticipation.status == "invited",
        )
    ).scalar_one_or_none()

    if participation is None:
        flash("Keine ausstehende Einladung gefunden.")
        return redirect(url_for("challenges.index"))

    db.session.delete(participation)
    db.session.commit()

    flash("Einladung abgelehnt.")
    return redirect(url_for("challenges.index"))


@challenges_bp.route("/<string:public_id>/bailout", methods=["POST"])
@login_required
def bailout(public_id):
    challenge = _get_challenge_by_public_id(public_id)

    participation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.challenge_id == challenge.id,
            ChallengeParticipation.status == "accepted",
        )
    ).scalar_one_or_none()

    if participation is None:
        flash("Du bist kein aktiver Teilnehmer dieser Challenge.")
        return redirect(url_for("challenges.detail", public_id=public_id))

    participation.status = "bailed_out"
    participation.bailed_out_at = datetime.now(timezone.utc)
    db.session.commit()

    flash(f"Du hast die Challenge verlassen. Bailout-Gebühr: {challenge.bailout_fee:.2f} €.")
    return redirect(url_for("challenges.detail", public_id=public_id))


@challenges_bp.route("/<string:public_id>/sick", methods=["POST"])
@login_required
def sick(public_id):
    challenge = _get_challenge_by_public_id(public_id)

    participation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.challenge_id == challenge.id,
            ChallengeParticipation.status == "accepted",
        )
    ).scalar_one_or_none()

    if participation is None:
        flash("Du bist kein aktiver Teilnehmer dieser Challenge.")
        return redirect(url_for("challenges.detail", public_id=public_id))

    today = date.today()
    week_start = today - __import__("datetime").timedelta(days=today.weekday())

    existing = db.session.execute(
        db.select(SickWeek).where(
            SickWeek.user_id == current_user.id,
            SickWeek.challenge_id == challenge.id,
            SickWeek.week_start == week_start,
        )
    ).scalar_one_or_none()

    if existing:
        flash("Du hast dich für diese Woche bereits krank gemeldet.")
        return redirect(url_for("challenges.detail", public_id=public_id))

    sick_week = SickWeek(
        user_id=current_user.id,
        challenge_id=challenge.id,
        week_start=week_start,
    )
    db.session.add(sick_week)
    db.session.commit()

    flash(f"Krankmeldung für die Woche ab {week_start.strftime('%d.%m.%Y')} eingetragen.")
    return redirect(url_for("challenges.detail", public_id=public_id))
