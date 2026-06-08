from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.activity import Activity
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.penalty import PenaltyOverride
from app.models.sick_period import SickPeriod
from app.services.penalty import get_week_mondays


def _sick_days_from_periods(periods: list, week_start: date) -> int:
    """Count sick days overlapping with the given week."""
    week_end = week_start + timedelta(days=6)
    total = 0
    for p in periods:
        if p.start_date <= week_end and p.end_date >= week_start:
            eff_start = max(p.start_date, week_start)
            eff_end = min(p.end_date, week_end)
            total += (eff_end - eff_start).days + 1
    return min(total, 7)


def _fulfilled_in_week(fulfilled_set: set, user_id: int, week_start: date) -> int:
    """Count fulfilled days within the week from a pre-loaded (user_id, date) set.

    Mirror of penalty.count_fulfilled_days but operates purely in memory.
    """
    return sum(
        1
        for i in range(7)
        if (user_id, week_start + timedelta(days=i)) in fulfilled_set
    )


def _weekly_penalty_pure(
    sick_days: int,
    override_amount: float | None,
    fulfilled: int,
    weekly_goal: int,
    penalty_per_miss: float,
) -> float:
    """Pure penalty calculation from already-resolved inputs.

    Byte-exact mirror of penalty.calculate_weekly_penalty's decision logic:
    SickPeriod deductions take precedence, then a PenaltyOverride, then
    missed-days * penalty. Kept in sync via
    test_weekly_summary.test_bulk_summary_matches_penalty_service.
    """
    if sick_days > 0:
        deductions = sick_days // 2
        effective_goal = max(0, weekly_goal - deductions)
        if effective_goal <= 0:
            return 0.0
        missed = max(0, effective_goal - fulfilled)
        return missed * penalty_per_miss

    if override_amount is not None:
        return override_amount

    missed = max(0, weekly_goal - fulfilled)
    return missed * penalty_per_miss


def get_challenge_summary(challenge: Challenge) -> dict:
    """Aggregate all participants across all weeks for the dashboard.

    Returns:
    {
        "challenge": Challenge,
        "weeks": [date, date, ...],  # Monday dates, only up to current week
        "participants": [
            {
                "user": User,
                "weekly_goal": int,
                "status": str,  # accepted, bailed_out
                "weeks": {
                    date: {
                        "fulfilled_days": int,
                        "is_sick": bool,
                        "penalty": float,
                        "overachieved": bool,  # True when fulfilled_days > weekly_goal
                    },
                    ...
                },
                "total_penalty": float,
            },
            ...
        ]
    }

    Performance: all per-(participant, week) data is resolved from three bulk
    queries (fulfilled days, sick periods, penalty overrides) and computed in
    memory, instead of issuing per-cell queries (former ~P*W*7 -> ~3 queries).
    """
    today = date.today()
    effective_end = min(today, challenge.end_date)

    # 1. All week Mondays up to the current/end date
    weeks = get_week_mondays(challenge.start_date, effective_end)

    # 2. All active/bailed-out participations (eager-load user)
    participations = (
        db.session.execute(
            db.select(ChallengeParticipation)
            .where(
                ChallengeParticipation.challenge_id == challenge.id,
                ChallengeParticipation.status.in_(["accepted", "bailed_out"]),
            )
            .options(joinedload(ChallengeParticipation.user))
        )
        .scalars()
        .all()
    )
    participant_ids = [p.user_id for p in participations]

    # 3. Bulk-load all data needed for penalty math in three queries.
    #    (a) Fulfilled days: one GROUP BY over all participants & days.
    fulfilled_set: set[tuple[int, date]] = set()
    overrides: dict[tuple[int, date], float] = {}
    sick_by_user: dict[int, list] = defaultdict(list)
    if participant_ids:
        fulfilled_rows = db.session.execute(
            db.select(Activity.user_id, Activity.activity_date)
            .where(
                Activity.challenge_id == challenge.id,
                Activity.user_id.in_(participant_ids),
            )
            .group_by(Activity.user_id, Activity.activity_date)
            .having(func.sum(Activity.duration_minutes) >= 30)
        ).all()
        fulfilled_set = {(uid, d) for uid, d in fulfilled_rows}

        # (b) All penalty overrides for these participants.
        override_rows = db.session.scalars(
            db.select(PenaltyOverride).where(
                PenaltyOverride.challenge_id == challenge.id,
                PenaltyOverride.user_id.in_(participant_ids),
            )
        ).all()
        overrides = {(o.user_id, o.week_start): o.override_amount for o in override_rows}

        # (c) All sick periods for these participants, grouped per user.
        all_sick_periods = db.session.scalars(
            db.select(SickPeriod).where(
                SickPeriod.challenge_id == challenge.id,
                SickPeriod.user_id.in_(participant_ids),
            )
        ).all()
        for sp in all_sick_periods:
            sick_by_user[sp.user_id].append(sp)

    # 4. Build per-participant data — all computation is in-memory now.
    participants_data = []
    for participation in participations:
        user = participation.user
        uid = user.id
        weekly_goal = participation.weekly_goal
        user_sick_periods = sick_by_user[uid]

        weeks_data: dict[date, dict] = {}
        total_penalty = 0.0

        for week_start in weeks:
            fulfilled_days = _fulfilled_in_week(fulfilled_set, uid, week_start)
            sick_days_val = _sick_days_from_periods(user_sick_periods, week_start)
            is_sick = sick_days_val > 0
            override_amount = (
                overrides.get((uid, week_start)) if sick_days_val == 0 else None
            )

            # Cell penalty uses the full weekly goal (potential weekly fine).
            penalty = _weekly_penalty_pure(
                sick_days_val,
                override_amount,
                fulfilled_days,
                weekly_goal,
                challenge.penalty_per_miss,
            )

            weeks_data[week_start] = {
                "fulfilled_days": fulfilled_days,
                "is_sick": is_sick,
                "sick_days": sick_days_val,
                "penalty": penalty,
                # "3+" indicator: participant exceeded weekly goal
                "overachieved": fulfilled_days > weekly_goal,
            }

            # Total penalty uses an elapsed-days adjusted goal and skips
            # future/partial weeks — mirror of penalty.calculate_total_penalty.
            if week_start > today:
                continue
            week_end = week_start + timedelta(days=6)
            effective_week_end = min(week_end, today - timedelta(days=1))
            elapsed_days = (effective_week_end - week_start).days + 1  # 1-7
            adjusted_goal = min(weekly_goal, elapsed_days)
            if adjusted_goal <= 0:
                continue
            total_penalty += _weekly_penalty_pure(
                sick_days_val,
                override_amount,
                fulfilled_days,
                adjusted_goal,
                challenge.penalty_per_miss,
            )

        # Bailout fee
        if participation.status == "bailed_out":
            total_penalty += challenge.bailout_fee

        participants_data.append(
            {
                "user": user,
                "weekly_goal": weekly_goal,
                "status": participation.status,
                "weeks": weeks_data,
                "total_penalty": total_penalty,
            }
        )

    # 5. Sort by total_penalty ascending (best performers first)
    participants_data.sort(key=lambda p: p["total_penalty"])

    return {
        "challenge": challenge,
        "weeks": weeks,
        "participants": participants_data,
    }
