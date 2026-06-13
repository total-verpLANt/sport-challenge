"""Tests for the challenge statistics service (Top-3 rankings).

Covers each statistic's ranking, the two streak variants (week-based bridging
sick periods, strict day-based), edge cases (no activities, NULL started_at,
ties) and a query-count guard against N+1 regressions — mirroring the approach
of test_weekly_summary.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import event

from app.extensions import db as _db
from app.models.activity import Activity, ActivityLike
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.sick_period import SickPeriod
from app.models.user import User
from app.services.statistics import get_challenge_statistics


def _user(db, email, nickname=None):
    u = User(email=email, nickname=nickname, is_approved=True)
    u.set_password("pass")
    db.session.add(u)
    db.session.commit()
    return u


def _activity(db, user, challenge, day, minutes, sport="running", started_at=None):
    a = Activity(
        user_id=user.id,
        challenge_id=challenge.id,
        activity_date=day,
        duration_minutes=minutes,
        sport_type=sport,
        source="manual",
        started_at=started_at,
    )
    db.session.add(a)
    db.session.commit()
    return a


def _challenge(db, admin, weeks_back=2, weeks_fwd=1):
    this_monday = date.today() - timedelta(days=date.today().weekday())
    start = this_monday - timedelta(weeks=weeks_back)
    end = this_monday + timedelta(weeks=weeks_fwd, days=6)
    c = Challenge(
        name="Stats Challenge",
        start_date=start,
        end_date=end,
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=admin.id,
    )
    db.session.add(c)
    db.session.commit()
    return c, start


def _stat(result, key):
    return next(s for s in result["stats"] if s["key"] == key)


def test_basic_rankings(app, db):
    """SUM-time, COUNT-activities, diversity, longest single session."""
    with app.app_context():
        admin = _user(db, "stats_admin@test.com")
        challenge, start = _challenge(db, admin)

        alice = _user(db, "alice@test.com", "Alice")
        bob = _user(db, "bob@test.com", "Bob")
        for u in (alice, bob):
            db.session.add(
                ChallengeParticipation(
                    user_id=u.id, challenge_id=challenge.id,
                    status="accepted", weekly_goal=3,
                )
            )
        db.session.commit()

        # Alice: 3 activities, total 150 min, 2 sports, max session 90
        _activity(db, alice, challenge, start, 30, "running")
        _activity(db, alice, challenge, start + timedelta(days=1), 30, "cycling")
        _activity(db, alice, challenge, start + timedelta(days=2), 90, "running")
        # Bob: 2 activities, total 60 min, 1 sport, max session 40
        _activity(db, bob, challenge, start, 20, "swimming")
        _activity(db, bob, challenge, start + timedelta(days=1), 40, "swimming")

        result = get_challenge_statistics(challenge)

        most_time = _stat(result, "most_time")["top"]
        assert most_time[0]["name"] == "Alice" and most_time[0]["value"] == 150
        assert most_time[1]["name"] == "Bob" and most_time[1]["value"] == 60

        most_act = _stat(result, "most_activities")["top"]
        assert most_act[0]["name"] == "Alice" and most_act[0]["value"] == 3

        diversity = _stat(result, "diversity")["top"]
        assert diversity[0]["name"] == "Alice" and diversity[0]["value"] == 2

        longest = _stat(result, "longest_session")["top"]
        assert longest[0]["name"] == "Alice" and longest[0]["value"] == 90
        assert "1 h 30 min" == longest[0]["display"]


def test_day_streak_strict(app, db):
    """Day streak counts consecutive calendar days with >=30 min; gaps break it."""
    with app.app_context():
        admin = _user(db, "ds_admin@test.com")
        challenge, start = _challenge(db, admin)
        u = _user(db, "streaker@test.com", "Streaker")
        db.session.add(
            ChallengeParticipation(
                user_id=u.id, challenge_id=challenge.id,
                status="accepted", weekly_goal=3,
            )
        )
        db.session.commit()

        # 4 consecutive days fulfilled, gap, then 2 more
        for off in range(4):
            _activity(db, u, challenge, start + timedelta(days=off), 30)
        for off in (6, 7):
            _activity(db, u, challenge, start + timedelta(days=off), 30)
        # A day below threshold must NOT count toward the streak.
        _activity(db, u, challenge, start + timedelta(days=9), 10)

        result = get_challenge_statistics(challenge)
        day_streak = _stat(result, "day_streak")["top"]
        assert day_streak[0]["value"] == 4


def test_week_streak_broken_by_sick(app, db):
    """Week streak: a sick/absence week breaks the run of fulfilled weeks."""
    with app.app_context():
        admin = _user(db, "ws_admin@test.com")
        # Need at least 3 fully-past weeks → anchor 4 weeks back.
        challenge, start = _challenge(db, admin, weeks_back=4, weeks_fwd=0)
        u = _user(db, "consistent@test.com", "Consistent")
        db.session.add(
            ChallengeParticipation(
                user_id=u.id, challenge_id=challenge.id,
                status="accepted", weekly_goal=2,
            )
        )
        db.session.commit()

        w0 = start
        w1 = start + timedelta(weeks=1)
        w2 = start + timedelta(weeks=2)

        # Week 0: goal met (2 fulfilled days)
        _activity(db, u, challenge, w0, 30)
        _activity(db, u, challenge, w0 + timedelta(days=1), 30)
        # Week 1: sick the whole week, no activity → breaks the streak
        db.session.add(
            SickPeriod(
                user_id=u.id, challenge_id=challenge.id,
                start_date=w1, end_date=w1 + timedelta(days=6),
            )
        )
        db.session.commit()
        # Week 2: goal met again
        _activity(db, u, challenge, w2, 30)
        _activity(db, u, challenge, w2 + timedelta(days=1), 30)

        result = get_challenge_statistics(challenge)
        week_streak = _stat(result, "week_streak")["top"]
        # An absence breaks the run: w0 (met) → w1 (sick, breaks) → w2 (met).
        # The longest unbroken run of fulfilled weeks is therefore 1.
        assert week_streak[0]["value"] == 1


def test_most_liked_and_time_of_day(app, db):
    """Most-liked activity ranking + early bird / night owl from started_at."""
    with app.app_context():
        admin = _user(db, "ml_admin@test.com")
        challenge, start = _challenge(db, admin)
        early = _user(db, "early@test.com", "Early")
        late = _user(db, "late@test.com", "Late")
        liker = _user(db, "liker@test.com", "Liker")
        for u in (early, late):
            db.session.add(
                ChallengeParticipation(
                    user_id=u.id, challenge_id=challenge.id,
                    status="accepted", weekly_goal=3,
                )
            )
        db.session.commit()

        # Early trains at 06:00, late at 22:00
        a_early = _activity(
            db, early, challenge, start, 30, "running",
            started_at=datetime(start.year, start.month, start.day, 6, 0),
        )
        _activity(
            db, late, challenge, start, 30, "running",
            started_at=datetime(start.year, start.month, start.day, 22, 0),
        )

        # Give the early activity 1 like
        db.session.add(ActivityLike(activity_id=a_early.id, user_id=liker.id))
        db.session.commit()

        result = get_challenge_statistics(challenge)

        early_bird = _stat(result, "early_bird")["top"]
        assert early_bird[0]["name"] == "Early"
        assert early_bird[0]["display"] == "06:00"

        night_owl = _stat(result, "night_owl")["top"]
        assert night_owl[0]["name"] == "Late"
        assert night_owl[0]["display"] == "22:00"

        most_liked = _stat(result, "most_liked")["top"]
        assert len(most_liked) == 1
        assert most_liked[0]["value"] == 1
        assert "Early" in most_liked[0]["name"]


def test_early_bird_night_owl_use_min_max_not_average(app, db):
    """Option B: Frühaufsteher = früheste, Nachteule = späteste Aktivität.

    Ein User mit gemischten Zeiten (06:00 + 16:00) muss als Frühaufsteher
    mit 06:00 (min) UND als Nachteule mit 16:00 (max) erscheinen – nicht
    mit dem Durchschnitt 11:00.
    """
    with app.app_context():
        admin = _user(db, "mm_admin@test.com")
        challenge, start = _challenge(db, admin)
        mixed = _user(db, "mixed@test.com", "Mixed")
        db.session.add(
            ChallengeParticipation(
                user_id=mixed.id, challenge_id=challenge.id,
                status="accepted", weekly_goal=3,
            )
        )
        db.session.commit()

        # Zwei Aktivitäten: früh um 06:00, spät um 16:00 → Schnitt wäre 11:00
        _activity(
            db, mixed, challenge, start, 30, "running",
            started_at=datetime(start.year, start.month, start.day, 6, 0),
        )
        _activity(
            db, mixed, challenge, start, 30, "cycling",
            started_at=datetime(start.year, start.month, start.day, 16, 0),
        )

        result = get_challenge_statistics(challenge)

        early_bird = _stat(result, "early_bird")["top"]
        assert early_bird[0]["name"] == "Mixed"
        assert early_bird[0]["display"] == "06:00"

        night_owl = _stat(result, "night_owl")["top"]
        assert night_owl[0]["name"] == "Mixed"
        assert night_owl[0]["display"] == "16:00"


def test_participants_overview(app, db):
    """Teilnehmer-Übersicht: Ø Start-Uhrzeit + Ø Dauer, inkl. User ohne Aktivität."""
    with app.app_context():
        admin = _user(db, "po_admin@test.com")
        challenge, start = _challenge(db, admin)
        active = _user(db, "active@test.com", "Aktiv")
        idle = _user(db, "idle@test.com", "Ohne")
        for u in (active, idle):
            db.session.add(
                ChallengeParticipation(
                    user_id=u.id, challenge_id=challenge.id,
                    status="accepted", weekly_goal=3,
                )
            )
        db.session.commit()

        # Aktiv: 06:00/30min + 16:00/90min → Ø-Start 11:00, Ø-Dauer 60 min
        _activity(
            db, active, challenge, start, 30, "running",
            started_at=datetime(start.year, start.month, start.day, 6, 0),
        )
        _activity(
            db, active, challenge, start, 90, "cycling",
            started_at=datetime(start.year, start.month, start.day, 16, 0),
        )

        result = get_challenge_statistics(challenge)
        by_name = {p["name"]: p for p in result["participants"]}

        # Sortierung nach Name (case-insensitiv): Aktiv vor Ohne
        assert [p["name"] for p in result["participants"]] == ["Aktiv", "Ohne"]

        assert by_name["Aktiv"]["avg_start"] == "11:00"
        assert by_name["Aktiv"]["avg_duration"] == "1 h"  # 60 min
        assert by_name["Aktiv"]["activity_count"] == 2

        # Teilnehmer ohne Aktivität: Platzhalter, count 0
        assert by_name["Ohne"]["avg_start"] == "–"
        assert by_name["Ohne"]["avg_duration"] == "–"
        assert by_name["Ohne"]["activity_count"] == 0


def test_empty_challenge_no_crash(app, db):
    """A challenge without participants/activities returns empty tops, no crash."""
    with app.app_context():
        admin = _user(db, "empty_admin@test.com")
        challenge, _ = _challenge(db, admin)
        result = get_challenge_statistics(challenge)
        assert len(result["stats"]) == 9
        for s in result["stats"]:
            assert s["top"] == []


def test_null_started_at_ignored(app, db):
    """Activities without started_at must not appear in early/night rankings."""
    with app.app_context():
        admin = _user(db, "null_admin@test.com")
        challenge, start = _challenge(db, admin)
        u = _user(db, "notime@test.com", "NoTime")
        db.session.add(
            ChallengeParticipation(
                user_id=u.id, challenge_id=challenge.id,
                status="accepted", weekly_goal=3,
            )
        )
        db.session.commit()
        _activity(db, u, challenge, start, 30, started_at=None)

        result = get_challenge_statistics(challenge)
        assert _stat(result, "early_bird")["top"] == []
        assert _stat(result, "night_owl")["top"] == []
        # but time/count still ranked
        assert _stat(result, "most_time")["top"][0]["name"] == "NoTime"


def test_invited_only_excluded(app, db):
    """Only accepted/bailed_out participants count; invited-only are ignored."""
    with app.app_context():
        admin = _user(db, "inv_admin@test.com")
        challenge, start = _challenge(db, admin)
        accepted = _user(db, "acc@test.com", "Accepted")
        invited = _user(db, "inv@test.com", "Invited")
        db.session.add_all([
            ChallengeParticipation(
                user_id=accepted.id, challenge_id=challenge.id,
                status="accepted", weekly_goal=3,
            ),
            ChallengeParticipation(
                user_id=invited.id, challenge_id=challenge.id,
                status="invited", weekly_goal=3,
            ),
        ])
        db.session.commit()
        _activity(db, accepted, challenge, start, 60)
        _activity(db, invited, challenge, start, 120)  # higher, but excluded

        result = get_challenge_statistics(challenge)
        most_time = _stat(result, "most_time")["top"]
        assert len(most_time) == 1
        assert most_time[0]["name"] == "Accepted"


def _count_queries(challenge):
    counter = {"n": 0}

    def _on_exec(conn, cur, stmt, params, ctx, executemany):
        counter["n"] += 1

    event.listen(_db.engine, "before_cursor_execute", _on_exec)
    try:
        get_challenge_statistics(challenge)
    finally:
        event.remove(_db.engine, "before_cursor_execute", _on_exec)
    return counter["n"]


def test_query_count_is_constant(app, db):
    """Statistics must not issue per-participant queries (N+1 guard)."""
    with app.app_context():
        admin = _user(db, "qc_stats_admin@test.com")

        def build(n, tag):
            challenge, start = _challenge(db, admin)
            challenge.name = tag
            db.session.commit()
            for i in range(n):
                u = _user(db, f"qc_{tag}_{i}@test.com")
                db.session.add(
                    ChallengeParticipation(
                        user_id=u.id, challenge_id=challenge.id,
                        status="accepted", weekly_goal=3,
                    )
                )
                db.session.commit()
                for off in range(3):
                    _activity(db, u, challenge, start + timedelta(days=off), 30)
            return challenge

        small = build(2, "small")
        large = build(8, "large")

        q_small = _count_queries(small)
        q_large = _count_queries(large)

        assert q_small == q_large, (
            f"query count scales with participants: {q_small} vs {q_large}"
        )
        # participations + activities + like counts + fulfilled + sick = ~5
        assert q_large <= 6, f"expected <=6 bulk queries, got {q_large}"
