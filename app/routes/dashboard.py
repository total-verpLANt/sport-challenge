from datetime import date

from flask import Blueprint, render_template
from flask_login import login_required

from app.extensions import db
from app.models.challenge import Challenge
from app.services.weekly_summary import get_challenge_summary

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
        return render_template("dashboard/index.html", summary=None)

    summary = get_challenge_summary(challenge)
    return render_template("dashboard/index.html", summary=summary)
