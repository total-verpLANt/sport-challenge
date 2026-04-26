"""Unit tests for the penalty service."""
from datetime import date, timedelta

import pytest

from app.models.activity import Activity
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.penalty import PenaltyOverride
from app.models.sick_week import SickWeek
from app.models.user import User
from app.services.penalty import (
    calculate_weekly_penalty,
    calculate_total_penalty,
    count_fulfilled_days,
    get_week_mondays,
)


def _make_challenge(db, start_date, end_date, penalty_per_miss=5.0):
    """Create a minimal challenge in the DB."""
    user = User(email=f"creator_{start_date}@test.com", is_approved=True)
    user.set_password("pass")
    db.session.add(user)
    db.session.commit()

    challenge = Challenge(
        name="Penalty Test Challenge",
        start_date=start_date,
        end_date=end_date,
        penalty_per_miss=penalty_per_miss,
        bailout_fee=25.0,
        created_by_id=user.id,
    )
    db.session.add(challenge)
    db.session.commit()
    return challenge


def _make_participant(db, challenge_id, weekly_goal=3):
    user = User(email=f"participant_{challenge_id}_{weekly_goal}@test.com", is_approved=True)
    user.set_password("pass")
    db.session.add(user)
    db.session.commit()

    participation = ChallengeParticipation(
        user_id=user.id,
        challenge_id=challenge_id,
        status="accepted",
        weekly_goal=weekly_goal,
    )
    db.session.add(participation)
    db.session.commit()
    return user, participation


def test_get_week_mondays(app):
    # A 2-week range: 2026-05-04 (Monday) to 2026-05-17 (Sunday)
    with app.app_context():
        start = date(2026, 5, 4)
        end = date(2026, 5, 17)
        mondays = get_week_mondays(start, end)
        assert mondays == [date(2026, 5, 4), date(2026, 5, 11)]


def test_no_penalty_when_goal_met(app, db):
    with app.app_context():
        week_start = date(2026, 5, 4)  # Monday
        challenge = _make_challenge(db, week_start, week_start + timedelta(days=13))
        user, participation = _make_participant(db, challenge.id, weekly_goal=3)

        # Add 3 activities on different days, each >= 30 min
        for offset in range(3):
            activity = Activity(
                user_id=user.id,
                challenge_id=challenge.id,
                activity_date=week_start + timedelta(days=offset),
                duration_minutes=30,
                sport_type="running",
                source="manual",
            )
            db.session.add(activity)
        db.session.commit()

        penalty = calculate_weekly_penalty(
            user_id=user.id,
            challenge_id=challenge.id,
            week_start=week_start,
            weekly_goal=3,
            penalty_per_miss=5.0,
        )
        assert penalty == 0.0


def test_penalty_for_missed_days(app, db):
    with app.app_context():
        week_start = date(2026, 5, 4)
        challenge = _make_challenge(db, week_start, week_start + timedelta(days=13))
        user, participation = _make_participant(db, challenge.id, weekly_goal=3)

        # Only 1 fulfilled day (1 of 3 goal days met)
        activity = Activity(
            user_id=user.id,
            challenge_id=challenge.id,
            activity_date=week_start,
            duration_minutes=45,
            sport_type="cycling",
            source="manual",
        )
        db.session.add(activity)
        db.session.commit()

        penalty = calculate_weekly_penalty(
            user_id=user.id,
            challenge_id=challenge.id,
            week_start=week_start,
            weekly_goal=3,
            penalty_per_miss=5.0,
        )
        # 2 missed days × 5€ = 10€
        assert penalty == 10.0


def test_max_penalty_capped(app, db):
    with app.app_context():
        week_start = date(2026, 5, 4)
        challenge = _make_challenge(db, week_start, week_start + timedelta(days=13))
        user, participation = _make_participant(db, challenge.id, weekly_goal=3)

        # No activities at all
        penalty = calculate_weekly_penalty(
            user_id=user.id,
            challenge_id=challenge.id,
            week_start=week_start,
            weekly_goal=3,
            penalty_per_miss=5.0,
        )
        # 3 missed days × 5€ = 15€
        assert penalty == 15.0


def test_sick_week_no_penalty(app, db):
    with app.app_context():
        week_start = date(2026, 5, 4)
        challenge = _make_challenge(db, week_start, week_start + timedelta(days=13))
        user, participation = _make_participant(db, challenge.id, weekly_goal=3)

        sick_week = SickWeek(
            user_id=user.id,
            challenge_id=challenge.id,
            week_start=week_start,
        )
        db.session.add(sick_week)
        db.session.commit()

        penalty = calculate_weekly_penalty(
            user_id=user.id,
            challenge_id=challenge.id,
            week_start=week_start,
            weekly_goal=3,
            penalty_per_miss=5.0,
        )
        assert penalty == 0.0


def test_penalty_override_applied(app, db):
    with app.app_context():
        week_start = date(2026, 5, 4)
        challenge = _make_challenge(db, week_start, week_start + timedelta(days=13))
        user, participation = _make_participant(db, challenge.id, weekly_goal=3)

        admin = User(email="override_admin@test.com", is_approved=True)
        admin.role = "admin"
        admin.set_password("pass")
        db.session.add(admin)
        db.session.commit()

        override = PenaltyOverride(
            user_id=user.id,
            challenge_id=challenge.id,
            week_start=week_start,
            override_amount=3.0,
            reason="Special case",
            set_by_id=admin.id,
        )
        db.session.add(override)
        db.session.commit()

        penalty = calculate_weekly_penalty(
            user_id=user.id,
            challenge_id=challenge.id,
            week_start=week_start,
            weekly_goal=3,
            penalty_per_miss=5.0,
        )
        assert penalty == 3.0


def test_two_per_week_goal(app, db):
    with app.app_context():
        week_start = date(2026, 5, 4)
        challenge = _make_challenge(db, week_start, week_start + timedelta(days=13))
        user, participation = _make_participant(db, challenge.id, weekly_goal=2)

        # 0 fulfilled days, goal=2 → 2 × 5€ = 10€
        penalty = calculate_weekly_penalty(
            user_id=user.id,
            challenge_id=challenge.id,
            week_start=week_start,
            weekly_goal=2,
            penalty_per_miss=5.0,
        )
        assert penalty == 10.0


def test_day_aggregation(app, db):
    with app.app_context():
        week_start = date(2026, 5, 4)
        challenge = _make_challenge(db, week_start, week_start + timedelta(days=13))
        user, participation = _make_participant(db, challenge.id, weekly_goal=1)

        # Two 20-min activities on same day → 40 min ≥ 30, counts as 1 fulfilled day
        for _ in range(2):
            activity = Activity(
                user_id=user.id,
                challenge_id=challenge.id,
                activity_date=week_start,
                duration_minutes=20,
                sport_type="yoga",
                source="manual",
            )
            db.session.add(activity)
        db.session.commit()

        fulfilled = count_fulfilled_days(user.id, challenge.id, week_start)
        assert fulfilled == 1

        penalty = calculate_weekly_penalty(
            user_id=user.id,
            challenge_id=challenge.id,
            week_start=week_start,
            weekly_goal=1,
            penalty_per_miss=5.0,
        )
        assert penalty == 0.0
