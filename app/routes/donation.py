"""Spendenziel-Vorschläge und -Abstimmung pro Challenge (Epic 1t8s).

Dieses Modul enthält die Seite mit den Spendenziel-Vorschlägen sowie die
Routen zum Anlegen und Löschen von Vorschlägen. Die Poll-Routen
(open/close/vote/unvote) folgen in einem separaten Issue.
"""
import uuid as _uuid

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db, limiter
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.donation import DonationPoll, DonationProposal, DonationVote
from app.models.user import User
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

    return render_template(
        "donation/index.html",
        challenge=challenge,
        proposals=proposals,
        authors=authors,
        poll=poll,
        vote_counts=vote_counts,
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
