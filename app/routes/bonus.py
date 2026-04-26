from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.bonus import BonusChallenge, BonusChallengeEntry
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.user import User
from app.utils.decorators import admin_required

bonus_bp = Blueprint("bonus", __name__, template_folder="../templates")


def format_time(seconds: float) -> str:
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{mins}:{secs:02d}"


def _get_active_challenge():
    """Return the most recent challenge, or None."""
    return db.session.execute(
        db.select(Challenge).order_by(Challenge.created_at.desc())
    ).scalars().first()


def _user_is_accepted_participant(challenge_id: int) -> bool:
    """Check if the current user has accepted participation in the given challenge."""
    participation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.challenge_id == challenge_id,
            ChallengeParticipation.status == "accepted",
        )
    ).scalar_one_or_none()
    return participation is not None


@bonus_bp.route("/")
@login_required
def index():
    active_challenge = _get_active_challenge()

    bonus_challenges = []
    if active_challenge:
        bonus_challenges = db.session.execute(
            db.select(BonusChallenge)
            .where(BonusChallenge.challenge_id == active_challenge.id)
            .order_by(BonusChallenge.scheduled_date)
        ).scalars().all()

    # Build ranking data per bonus challenge
    rankings = {}
    user_entries = {}
    for bc in bonus_challenges:
        entries = db.session.execute(
            db.select(BonusChallengeEntry)
            .where(BonusChallengeEntry.bonus_challenge_id == bc.id)
            .order_by(BonusChallengeEntry.time_seconds)
        ).scalars().all()

        ranked = []
        for entry in entries:
            user = db.session.get(User, entry.user_id)
            ranked.append({
                "user_id": entry.user_id,
                "email": user.email if user else "Unbekannt",
                "time_seconds": entry.time_seconds,
                "time_formatted": format_time(entry.time_seconds),
            })
        rankings[bc.id] = ranked

        # Track whether current user has an entry
        user_entry = db.session.execute(
            db.select(BonusChallengeEntry).where(
                BonusChallengeEntry.bonus_challenge_id == bc.id,
                BonusChallengeEntry.user_id == current_user.id,
            )
        ).scalar_one_or_none()
        user_entries[bc.id] = user_entry

    # Check if current user is an accepted participant (for entry form visibility)
    is_participant = False
    if active_challenge:
        is_participant = _user_is_accepted_participant(active_challenge.id)

    return render_template(
        "bonus/index.html",
        active_challenge=active_challenge,
        bonus_challenges=bonus_challenges,
        rankings=rankings,
        user_entries=user_entries,
        is_participant=is_participant,
    )


@bonus_bp.route("/create")
@admin_required
def create():
    active_challenge = _get_active_challenge()
    if not active_challenge:
        flash("Es gibt noch keine aktive Challenge. Bitte zuerst eine Challenge erstellen.")
        return redirect(url_for("bonus.index"))
    return render_template("bonus/create.html", active_challenge=active_challenge)


@bonus_bp.route("/create", methods=["POST"])
@admin_required
def create_post():
    active_challenge = _get_active_challenge()
    if not active_challenge:
        flash("Es gibt noch keine aktive Challenge.")
        return redirect(url_for("bonus.index"))

    scheduled_date_str = request.form.get("scheduled_date", "").strip()
    description = request.form.get("description", "").strip()

    errors = []
    if not scheduled_date_str:
        errors.append("Datum darf nicht leer sein.")
    if not description:
        errors.append("Beschreibung darf nicht leer sein.")

    scheduled_date_val = None
    if scheduled_date_str:
        try:
            scheduled_date_val = date.fromisoformat(scheduled_date_str)
        except ValueError:
            errors.append("Ungültiges Datum.")

    if errors:
        for error in errors:
            flash(error)
        return render_template(
            "bonus/create.html",
            active_challenge=active_challenge,
            form_data=request.form,
        )

    bonus_challenge = BonusChallenge(
        challenge_id=active_challenge.id,
        scheduled_date=scheduled_date_val,
        description=description,
    )
    db.session.add(bonus_challenge)
    db.session.commit()

    flash(f"Bonus-Challenge '{description}' am {scheduled_date_val.strftime('%d.%m.%Y')} wurde erstellt.")
    return redirect(url_for("bonus.index"))


@bonus_bp.route("/<int:bonus_id>/entry", methods=["POST"])
@login_required
def add_entry(bonus_id):
    bonus_challenge = db.session.get(BonusChallenge, bonus_id)
    if bonus_challenge is None:
        flash("Bonus-Challenge nicht gefunden.")
        return redirect(url_for("bonus.index"))

    # Check that user is accepted participant
    if not _user_is_accepted_participant(bonus_challenge.challenge_id):
        flash("Du bist kein akzeptierter Teilnehmer dieser Challenge.")
        return redirect(url_for("bonus.index"))

    time_str = request.form.get("time", "").strip()
    if not time_str:
        flash("Bitte eine Zeit eingeben.")
        return redirect(url_for("bonus.index"))

    try:
        if ":" in time_str:
            parts = time_str.split(":")
            total_seconds = int(parts[0]) * 60 + int(parts[1])
        else:
            total_seconds = float(time_str)
    except (ValueError, IndexError):
        flash("Ungültiges Zeitformat. Bitte M:SS oder Sekunden eingeben (z.B. '2:35' oder '155').")
        return redirect(url_for("bonus.index"))

    if total_seconds <= 0:
        flash("Die Zeit muss größer als 0 sein.")
        return redirect(url_for("bonus.index"))

    entry = BonusChallengeEntry(
        user_id=current_user.id,
        bonus_challenge_id=bonus_id,
        time_seconds=total_seconds,
    )
    db.session.add(entry)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Du hast bereits eine Zeit für diese Bonus-Challenge eingetragen.")
        return redirect(url_for("bonus.index"))

    flash(f"Zeit {format_time(total_seconds)} erfolgreich eingetragen.")
    return redirect(url_for("bonus.index"))
