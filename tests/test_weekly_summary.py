"""Regression tests for the dashboard weekly_summary service.

The service was optimised to resolve all per-(participant, week) data from a
few bulk queries and compute penalties in memory, instead of issuing per-cell
queries. These tests pin that the in-memory bulk path produces byte-identical
results to the canonical per-row penalty.py functions, so the two can never
silently drift apart.
"""
from datetime import date, timedelta

from sqlalchemy import event

from app.extensions import db as _db
from app.models.activity import Activity
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.penalty import PenaltyOverride
from app.models.sick_period import SickPeriod
from app.models.user import User
from app.services.penalty import (
    calculate_total_penalty,
    calculate_weekly_penalty,
    count_fulfilled_days,
)
from app.services.weekly_summary import get_challenge_summary


def _user(db, email):
    u = User(email=email, is_approved=True)
    u.set_password("pass")
    db.session.add(u)
    db.session.commit()
    return u


def _activity(db, user, challenge, day, minutes):
    db.session.add(
        Activity(
            user_id=user.id,
            challenge_id=challenge.id,
            activity_date=day,
            duration_minutes=minutes,
            sport_type="running",
            source="manual",
        )
    )


def test_bulk_summary_matches_penalty_service(app, db):
    """get_challenge_summary (bulk) == calculate_weekly_penalty/_total (per-row).

    Builds a deliberately mixed scenario spanning three weeks with activities,
    a sick period, a penalty override and a bailed-out participant, then asserts
    every cell penalty, fulfilled-day count and total matches the canonical
    penalty.py path exactly.
    """
    with app.app_context():
        # Anchor the challenge so "today" sits in the third week → past weeks
        # are fully counted, the current week is partially elapsed.
        this_monday = date.today() - timedelta(days=date.today().weekday())
        start = this_monday - timedelta(weeks=2)
        end = this_monday + timedelta(weeks=2, days=6)

        admin = _user(db, "summary_admin@test.com")
        challenge = Challenge(
            name="Bulk Summary Challenge",
            start_date=start,
            end_date=end,
            penalty_per_miss=5.0,
            bailout_fee=25.0,
            created_by_id=admin.id,
        )
        db.session.add(challenge)
        db.session.commit()

        w0 = start                       # week 1 (fully past)
        w1 = start + timedelta(weeks=1)  # week 2 (fully past)

        # Participant A (goal 3): full week-1, partial week-2, nothing else.
        a = _user(db, "summary_a@test.com")
        pa = ChallengeParticipation(
            user_id=a.id, challenge_id=challenge.id, status="accepted", weekly_goal=3
        )
        for off in range(3):
            _activity(db, a, challenge, w0 + timedelta(days=off), 30)
        _activity(db, a, challenge, w1, 45)
        # Same-day aggregation: 2x20 min on one day counts once.
        _activity(db, a, challenge, w1 + timedelta(days=1), 20)
        _activity(db, a, challenge, w1 + timedelta(days=1), 20)

        # Participant B (goal 2): sick in week-1, override in week-2, bailed out.
        b = _user(db, "summary_b@test.com")
        pb = ChallengeParticipation(
            user_id=b.id, challenge_id=challenge.id, status="bailed_out", weekly_goal=2
        )
        db.session.add(
            SickPeriod(
                user_id=b.id,
                challenge_id=challenge.id,
                start_date=w0,
                end_date=w0 + timedelta(days=3),  # 4 sick days
            )
        )
        db.session.add(
            PenaltyOverride(
                user_id=b.id,
                challenge_id=challenge.id,
                week_start=w1,
                override_amount=7.0,
                reason="manual adjust",
                set_by_id=admin.id,
            )
        )

        # Participant C (goal 3): no activity at all → full penalties.
        c = _user(db, "summary_c@test.com")
        pc = ChallengeParticipation(
            user_id=c.id, challenge_id=challenge.id, status="accepted", weekly_goal=3
        )

        # Invited-only user must be ignored by the summary entirely.
        d = _user(db, "summary_d@test.com")
        pd = ChallengeParticipation(
            user_id=d.id, challenge_id=challenge.id, status="invited", weekly_goal=3
        )

        db.session.add_all([pa, pb, pc, pd])
        db.session.commit()

        summary = get_challenge_summary(challenge)

        # Invited-only participant is excluded.
        emails = {p["user"].email for p in summary["participants"]}
        assert emails == {
            "summary_a@test.com",
            "summary_b@test.com",
            "summary_c@test.com",
        }

        parts = {
            a.id: pa,
            b.id: pb,
            c.id: pc,
        }
        for entry in summary["participants"]:
            user = entry["user"]
            participation = parts[user.id]

            # Total penalty must match the canonical per-row computation.
            expected_total = calculate_total_penalty(user.id, challenge, participation)
            assert entry["total_penalty"] == expected_total, (
                f"total mismatch for {user.email}"
            )

            # Every cell must match fulfilled-days and full-goal weekly penalty.
            for week_start, cell in entry["weeks"].items():
                expected_fulfilled = count_fulfilled_days(
                    user.id, challenge.id, week_start
                )
                expected_penalty = calculate_weekly_penalty(
                    user_id=user.id,
                    challenge_id=challenge.id,
                    week_start=week_start,
                    weekly_goal=participation.weekly_goal,
                    penalty_per_miss=challenge.penalty_per_miss,
                )
                assert cell["fulfilled_days"] == expected_fulfilled, (
                    f"fulfilled mismatch {user.email} @ {week_start}"
                )
                assert cell["penalty"] == expected_penalty, (
                    f"cell penalty mismatch {user.email} @ {week_start}"
                )

        # Sanity: ordering is ascending by total penalty.
        totals = [p["total_penalty"] for p in summary["participants"]]
        assert totals == sorted(totals)


def _seed_participants(db, challenge, n, start):
    """Create n accepted participants each with a few activities."""
    for i in range(n):
        u = _user(db, f"qc_{challenge.id}_{i}@test.com")
        db.session.add(
            ChallengeParticipation(
                user_id=u.id,
                challenge_id=challenge.id,
                status="accepted",
                weekly_goal=3,
            )
        )
        for w in range(3):
            for off in range(2):
                _activity(
                    db, u, challenge, start + timedelta(weeks=w, days=off), 30
                )
    db.session.commit()


def _count_summary_queries(db, challenge):
    counter = {"n": 0}

    def _on_exec(conn, cur, stmt, params, ctx, executemany):
        counter["n"] += 1

    event.listen(db.engine, "before_cursor_execute", _on_exec)
    try:
        get_challenge_summary(challenge)
    finally:
        event.remove(db.engine, "before_cursor_execute", _on_exec)
    return counter["n"]


def _make_qc_challenge(db, n_participants):
    this_monday = date.today() - timedelta(days=date.today().weekday())
    start = this_monday - timedelta(weeks=2)
    end = this_monday + timedelta(weeks=1, days=6)
    admin = _user(db, f"qc_admin_{n_participants}@test.com")
    challenge = Challenge(
        name=f"QC {n_participants}",
        start_date=start,
        end_date=end,
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=admin.id,
    )
    db.session.add(challenge)
    db.session.commit()
    _seed_participants(db, challenge, n_participants, start)
    return challenge


def test_summary_query_count_is_constant(app, db):
    """get_challenge_summary must not issue per-(participant, week) queries.

    The query count must stay constant regardless of participant count — a
    guard against re-introducing the N+1 pattern this optimisation removed.
    """
    with app.app_context():
        small = _make_qc_challenge(db, 2)
        large = _make_qc_challenge(db, 8)

        q_small = _count_summary_queries(_db, small)
        q_large = _count_summary_queries(_db, large)

        # Same number of queries for 2 vs 8 participants → no N+1.
        assert q_small == q_large, (
            f"query count scales with participants: {q_small} vs {q_large}"
        )
        # Bulk design: participations + fulfilled + overrides + sick periods.
        assert q_large <= 5, f"expected <=5 bulk queries, got {q_large}"
