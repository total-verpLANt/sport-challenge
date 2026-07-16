"""Spendenziel-Vorschläge und -Abstimmung pro Challenge (Epic 1t8s).

Dieses Modul enthält die Seite mit den Spendenziel-Vorschlägen, die Routen
zum Anlegen und Löschen von Vorschlägen sowie die Poll-Routen
(open/close/vote/unvote) mit Live-Zwischenstand.
"""
import uuid as _uuid
from datetime import date, datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.extensions import db, limiter
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.donation import DonationPoll, DonationProposal, DonationVote
from app.models.user import User
from app.services import notifications as notif_service
from app.services.notifications import NotificationType
from app.utils.decorators import admin_required
from app.utils.urls import is_safe_external_url

donation_bp = Blueprint("donation", __name__, template_folder="../templates")


def _get_challenge_by_public_id(public_id: str) -> Challenge:
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


def _user_is_participant(challenge_id: int) -> bool:
    """Teilnehmer-Check: accepted ODER bailed_out (Ausgestiegene haben eingezahlt)."""
    participation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.challenge_id == challenge_id,
            ChallengeParticipation.status.in_(["accepted", "bailed_out"]),
        )
    ).scalar_one_or_none()
    return participation is not None


def _get_poll(challenge_id: int) -> DonationPoll | None:
    return db.session.execute(
        db.select(DonationPoll).where(DonationPoll.challenge_id == challenge_id)
    ).scalar_one_or_none()


def _vote_counts(poll: DonationPoll) -> dict[int, int]:
    """Stimmenzahl je Vorschlag der Poll-Challenge (proposal_id -> count)."""
    rows = db.session.execute(
        db.select(DonationVote.proposal_id, func.count())
        .join(DonationProposal, DonationVote.proposal_id == DonationProposal.id)
        .where(DonationProposal.challenge_id == poll.challenge_id)
        .group_by(DonationVote.proposal_id)
    ).all()
    return {proposal_id: count for proposal_id, count in rows}


def _tie_proposal_ids(vote_counts: dict[int, int]) -> list[int]:
    """IDs der punktgleichen Erstplatzierten – leer, wenn das Maximum eindeutig ist."""
    if not vote_counts:
        return []
    max_count = max(vote_counts.values())
    top = [proposal_id for proposal_id, count in vote_counts.items() if count == max_count]
    return top if len(top) > 1 else []


def _render_index(challenge: Challenge, form_data=None, status_code: int = 200):
    proposals = db.session.scalars(
        db.select(DonationProposal)
        .where(DonationProposal.challenge_id == challenge.id)
        .order_by(DonationProposal.created_at.asc(), DonationProposal.id.asc())
    ).all()

    authors = {}
    for proposal in proposals:
        if proposal.created_by_id not in authors:
            user = db.session.get(User, proposal.created_by_id)
            authors[proposal.created_by_id] = user.display_name if user else "Unbekannt"

    poll = _get_poll(challenge.id)
    vote_counts = _vote_counts(poll) if poll else {}
    total_votes = sum(vote_counts.values())

    my_vote_ids: set[int] = set()
    tie_proposal_ids: list[int] = []
    winner_proposal = None
    if poll is not None:
        my_vote_ids = set(
            db.session.scalars(
                db.select(DonationVote.proposal_id)
                .join(DonationProposal, DonationVote.proposal_id == DonationProposal.id)
                .where(
                    DonationVote.user_id == current_user.id,
                    DonationProposal.challenge_id == challenge.id,
                )
            ).all()
        )
        if poll.status == "open":
            tie_proposal_ids = _tie_proposal_ids(vote_counts)
        if poll.winner_proposal_id is not None:
            winner_proposal = db.session.get(DonationProposal, poll.winner_proposal_id)

    return render_template(
        "donation/index.html",
        challenge=challenge,
        proposals=proposals,
        authors=authors,
        poll=poll,
        vote_counts=vote_counts,
        total_votes=total_votes,
        my_vote_ids=my_vote_ids,
        tie_proposal_ids=tie_proposal_ids,
        winner_proposal=winner_proposal,
        today=date.today(),
        is_participant=_user_is_participant(challenge.id),
        form_data=form_data,
    ), status_code


@donation_bp.route("/<string:public_id>")
@login_required
def index(public_id):
    challenge = _get_challenge_by_public_id(public_id)

    my_participation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.challenge_id == challenge.id,
        )
    ).scalar_one_or_none()

    # Sichtbarkeitsprüfung: nicht-öffentliche Challenges nur für Teilnehmer/Admin
    if not challenge.is_public and not current_user.is_admin and my_participation is None:
        abort(403)

    return _render_index(challenge)


@donation_bp.route("/<string:public_id>/proposals", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def create_proposal(public_id):
    challenge = _get_challenge_by_public_id(public_id)

    if not _user_is_participant(challenge.id):
        flash("Du bist kein Teilnehmer dieser Challenge.")
        return redirect(url_for("donation.index", public_id=str(challenge.public_id)))

    if _get_poll(challenge.id) is not None:
        flash("Abstimmung läuft bereits – keine neuen Vorschläge.")
        return redirect(url_for("donation.index", public_id=str(challenge.public_id)))

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip() or None
    url = request.form.get("url", "").strip() or None

    errors = []
    if not name:
        errors.append("Name darf nicht leer sein.")
    elif len(name) > 255:
        errors.append("Name ist zu lang (max. 255 Zeichen).")
    if description and len(description) > 2000:
        errors.append("Beschreibung ist zu lang (max. 2000 Zeichen).")
    if url and not is_safe_external_url(url):
        errors.append("Link muss mit http:// oder https:// beginnen.")

    if errors:
        for error in errors:
            flash(error)
        return _render_index(challenge, form_data=request.form, status_code=400)

    proposal = DonationProposal(
        challenge_id=challenge.id,
        created_by_id=current_user.id,
        name=name,
        description=description,
        url=url,
    )
    db.session.add(proposal)
    db.session.commit()

    flash("Spendenziel-Vorschlag wurde angelegt.", "success")
    return redirect(url_for("donation.index", public_id=str(challenge.public_id)))


@donation_bp.route("/proposals/<int:proposal_id>/delete", methods=["POST"])
@login_required
def delete_proposal(proposal_id: int):
    proposal = db.session.get(DonationProposal, proposal_id)
    if proposal is None:
        abort(404)

    challenge = db.session.get(Challenge, proposal.challenge_id)
    poll = _get_poll(proposal.challenge_id)

    # Admin darf immer löschen (Moderation; Votes cascaden per FK).
    # Der Eigner nur, solange keine Abstimmung existiert.
    if not current_user.is_admin:
        if proposal.created_by_id != current_user.id or poll is not None:
            abort(403)

    db.session.delete(proposal)
    db.session.commit()

    flash("Vorschlag wurde gelöscht.", "success")
    return redirect(url_for("donation.index", public_id=str(challenge.public_id)))


@donation_bp.route("/<string:public_id>/poll/open", methods=["POST"])
@admin_required
def open_poll(public_id):
    challenge = _get_challenge_by_public_id(public_id)
    index_redirect = redirect(url_for("donation.index", public_id=str(challenge.public_id)))

    if challenge.end_date >= date.today():
        flash("Die Challenge läuft noch – Abstimmung erst nach dem Ende.")
        return index_redirect

    proposal_count = db.session.scalar(
        db.select(func.count())
        .select_from(DonationProposal)
        .where(DonationProposal.challenge_id == challenge.id)
    )
    if not proposal_count:
        flash("Es gibt noch keine Vorschläge – Abstimmung kann nicht gestartet werden.")
        return index_redirect

    try:
        max_votes = int(request.form.get("max_votes_per_user", "1"))
    except (TypeError, ValueError):
        flash("Ungültige Stimmenzahl.")
        return index_redirect
    if max_votes < 1:
        flash("Die Stimmenzahl pro Person muss mindestens 1 sein.")
        return index_redirect
    if max_votes > proposal_count:
        flash(
            f"Die Stimmenzahl pro Person darf die Anzahl der Vorschläge "
            f"({proposal_count}) nicht überschreiten."
        )
        return index_redirect

    poll = DonationPoll(
        challenge_id=challenge.id,
        status="open",
        max_votes_per_user=max_votes,
        created_by_id=current_user.id,
    )
    db.session.add(poll)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Abstimmung existiert bereits.")
        return index_redirect

    # Teilnehmer benachrichtigen (accepted + bailed_out, ohne den Öffner).
    # Message enthält nur den admin-kontrollierten Challenge-Namen –
    # NIE Vorschlags-Freitext (XSS-Invariante, siehe notifications.py).
    participant_ids = db.session.scalars(
        db.select(ChallengeParticipation.user_id).where(
            ChallengeParticipation.challenge_id == challenge.id,
            ChallengeParticipation.status.in_(["accepted", "bailed_out"]),
            ChallengeParticipation.user_id != current_user.id,
        )
    ).all()
    for user_id in participant_ids:
        notif_service.create_notification(
            user_id,
            NotificationType.DONATION_POLL_OPENED,
            f"Die Abstimmung über das Spendenziel der Challenge „{challenge.name}“ "
            f"ist eröffnet – stimme jetzt ab!",
            link_url=url_for("donation.index", public_id=str(challenge.public_id)),
            actor_id=current_user.id,
        )
    if participant_ids:
        db.session.commit()

    flash("Die Abstimmung über das Spendenziel wurde gestartet.", "success")
    return index_redirect


@donation_bp.route("/<string:public_id>/poll/close", methods=["POST"])
@admin_required
def close_poll(public_id):
    challenge = _get_challenge_by_public_id(public_id)
    index_redirect = redirect(url_for("donation.index", public_id=str(challenge.public_id)))

    poll = _get_poll(challenge.id)
    if poll is None or poll.status != "open":
        flash("Es gibt keine offene Abstimmung zum Schließen.")
        return index_redirect

    vote_counts = _vote_counts(poll)
    total_votes = sum(vote_counts.values())

    if total_votes == 0:
        poll.status = "closed"
        poll.closed_at = datetime.now(timezone.utc)
        db.session.commit()
        flash("Die Abstimmung wurde ohne Stimmen beendet – es gibt keinen Gewinner.")
        return index_redirect

    tie_ids = _tie_proposal_ids(vote_counts)
    if not tie_ids:
        # Eindeutiges Maximum → Gewinner automatisch setzen
        max_count = max(vote_counts.values())
        winner_id = next(
            proposal_id for proposal_id, count in vote_counts.items() if count == max_count
        )
    else:
        # Gleichstand an der Spitze: Admin muss den Gewinner auswählen
        raw_winner = request.form.get("winner_proposal_id", "").strip()
        if not raw_winner:
            flash("Gleichstand – bitte Gewinner auswählen.")
            return index_redirect
        try:
            winner_id = int(raw_winner)
        except ValueError:
            flash("Ungültige Gewinner-Auswahl.")
            return index_redirect
        if winner_id not in tie_ids:
            flash("Der gewählte Gewinner gehört nicht zu den punktgleichen Erstplatzierten.")
            return index_redirect

    poll.winner_proposal_id = winner_id
    poll.status = "closed"
    poll.closed_at = datetime.now(timezone.utc)
    db.session.commit()

    flash("Die Abstimmung wurde geschlossen – der Gewinner steht fest.", "success")
    return index_redirect


@donation_bp.route("/proposals/<int:proposal_id>/vote", methods=["POST"])
@login_required
@limiter.limit("30/minute")
def vote(proposal_id: int):
    proposal = db.session.get(DonationProposal, proposal_id)
    if proposal is None:
        abort(404)

    challenge = db.session.get(Challenge, proposal.challenge_id)
    index_redirect = redirect(url_for("donation.index", public_id=str(challenge.public_id)))

    if not _user_is_participant(challenge.id):
        flash("Du bist kein Teilnehmer dieser Challenge.")
        return index_redirect

    poll = _get_poll(challenge.id)
    if poll is None or poll.status != "open":
        flash("Es läuft gerade keine Abstimmung.")
        return index_redirect

    my_vote_count = db.session.scalar(
        db.select(func.count())
        .select_from(DonationVote)
        .join(DonationProposal, DonationVote.proposal_id == DonationProposal.id)
        .where(
            DonationVote.user_id == current_user.id,
            DonationProposal.challenge_id == challenge.id,
        )
    )
    if my_vote_count >= poll.max_votes_per_user:
        flash(f"Du hast bereits alle Stimmen vergeben (max. {poll.max_votes_per_user}).")
        return index_redirect

    db.session.add(DonationVote(user_id=current_user.id, proposal_id=proposal.id))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Du hast für dieses Ziel bereits gestimmt.")
        return index_redirect

    flash("Deine Stimme wurde gezählt.", "success")
    return index_redirect


@donation_bp.route("/proposals/<int:proposal_id>/unvote", methods=["POST"])
@login_required
def unvote(proposal_id: int):
    proposal = db.session.get(DonationProposal, proposal_id)
    if proposal is None:
        abort(404)

    challenge = db.session.get(Challenge, proposal.challenge_id)
    index_redirect = redirect(url_for("donation.index", public_id=str(challenge.public_id)))

    poll = _get_poll(challenge.id)
    if poll is None or poll.status != "open":
        flash("Die Abstimmung ist nicht mehr offen – Stimmen können nicht geändert werden.")
        return index_redirect

    my_vote = db.session.execute(
        db.select(DonationVote).where(
            DonationVote.user_id == current_user.id,
            DonationVote.proposal_id == proposal.id,
        )
    ).scalar_one_or_none()
    if my_vote is None:
        abort(404)

    db.session.delete(my_vote)
    db.session.commit()

    flash("Deine Stimme wurde zurückgezogen.", "success")
    return index_redirect
