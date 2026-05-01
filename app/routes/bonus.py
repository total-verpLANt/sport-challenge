from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.bonus import BonusChallenge, BonusChallengeEntry
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.user import User
from app.utils.decorators import admin_required
from app.utils.uploads import delete_upload, extract_video_recorded_at, get_media_type, save_upload

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
                "display_name": user.display_name if user else "Unbekannt",
                "time_seconds": entry.time_seconds,
                "time_formatted": format_time(entry.time_seconds),
                "recorded_at": entry.recorded_at,
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

    # Wanderpokal: beste Zeit pro User über alle Bonus-Challenges dieser Challenge
    overall_ranking = []
    if active_challenge and bonus_challenges:
        all_entries = db.session.execute(
            db.select(BonusChallengeEntry)
            .join(BonusChallenge, BonusChallengeEntry.bonus_challenge_id == BonusChallenge.id)
            .where(BonusChallenge.challenge_id == active_challenge.id)
        ).scalars().all()

        best_per_user: dict[int, float] = {}
        for entry in all_entries:
            if entry.user_id not in best_per_user or entry.time_seconds < best_per_user[entry.user_id]:
                best_per_user[entry.user_id] = entry.time_seconds

        for user_id, best_time in sorted(best_per_user.items(), key=lambda x: x[1]):
            user = db.session.get(User, user_id)
            overall_ranking.append({
                "user_id": user_id,
                "display_name": user.display_name if user else "Unbekannt",
                "time_seconds": best_time,
                "time_formatted": format_time(best_time),
            })

    return render_template(
        "bonus/index.html",
        active_challenge=active_challenge,
        bonus_challenges=bonus_challenges,
        rankings=rankings,
        user_entries=user_entries,
        is_participant=is_participant,
        overall_ranking=overall_ranking,
        today_date=date.today(),
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

    description = request.form.get("description", "").strip()
    date_strings = [s.strip() for s in request.form.getlist("scheduled_date") if s.strip()]

    errors = []
    if not description:
        errors.append("Beschreibung darf nicht leer sein.")
    if not date_strings:
        errors.append("Mindestens ein Datum muss angegeben werden.")

    parsed_dates = []
    for ds in date_strings:
        try:
            parsed_dates.append(date.fromisoformat(ds))
        except ValueError:
            errors.append(f"Ungültiges Datum: {ds}")

    if errors:
        for error in errors:
            flash(error)
        return render_template(
            "bonus/create.html",
            active_challenge=active_challenge,
            form_data=request.form,
        )

    for d in parsed_dates:
        db.session.add(BonusChallenge(
            challenge_id=active_challenge.id,
            scheduled_date=d,
            description=description,
        ))
    db.session.commit()

    dates_str = ", ".join(d.strftime("%d.%m.%Y") for d in sorted(parsed_dates))
    flash(f"Bonus-Challenge '{description}' wurde für {len(parsed_dates)} Datum/Daten erstellt: {dates_str}")
    return redirect(url_for("bonus.index"))


@bonus_bp.route("/<int:bonus_id>/delete", methods=["POST"])
@admin_required
def delete_bonus_challenge(bonus_id: int):
    bonus = db.session.get(BonusChallenge, bonus_id)
    if bonus is None:
        abort(404)
    # Video-Dateien vom Disk löschen bevor Entries aus DB entfernt werden
    entries = BonusChallengeEntry.query.filter_by(bonus_challenge_id=bonus.id).all()
    for entry in entries:
        if entry.video_path:
            delete_upload(entry.video_path)
    BonusChallengeEntry.query.filter_by(bonus_challenge_id=bonus.id).delete()
    db.session.delete(bonus)
    db.session.commit()
    flash("Bonus-Challenge wurde gelöscht.", "success")
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

    # Beweisvideo ist Pflicht
    video_file = request.files.get("video")
    if not video_file or not video_file.filename:
        flash("Bitte ein Beweisvideo hochladen.")
        return redirect(url_for("bonus.index"))

    video_path = save_upload(video_file)
    if video_path is None:
        flash("Ungültiges Videoformat (erlaubt: MP4, MOV, WebM, max. 50 MB).")
        return redirect(url_for("bonus.index"))

    if get_media_type(video_file.filename) != "video":
        delete_upload(video_path)
        flash("Nur Videodateien sind erlaubt (MP4, MOV, WebM).")
        return redirect(url_for("bonus.index"))

    recorded_at = extract_video_recorded_at(video_path)

    entry = BonusChallengeEntry(
        user_id=current_user.id,
        bonus_challenge_id=bonus_id,
        time_seconds=total_seconds,
        video_path=video_path,
        recorded_at=recorded_at,
    )
    db.session.add(entry)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        delete_upload(video_path)
        flash("Du hast bereits eine Zeit für diese Bonus-Challenge eingetragen.")
        return redirect(url_for("bonus.index"))

    flash(f"Zeit {format_time(total_seconds)} erfolgreich eingetragen.")
    return redirect(url_for("bonus.index"))
