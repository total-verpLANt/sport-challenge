from datetime import date, timedelta
from sqlalchemy import func
from app.extensions import db
from app.models.activity import Activity
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.sick_period import SickPeriod
from app.models.penalty import PenaltyOverride


def get_week_mondays(start_date: date, end_date: date) -> list[date]:
    """Returns all Mondays within the challenge period."""
    # Start from the Monday of start_date's week
    monday = start_date - timedelta(days=start_date.weekday())
    mondays = []
    current = monday
    while current <= end_date:
        mondays.append(current)
        current += timedelta(weeks=1)
    return mondays


def count_fulfilled_days(user_id: int, challenge_id: int, week_start: date) -> int:
    """Count days in the week where total duration >= 30 minutes."""
    week_end = week_start + timedelta(days=6)
    result = db.session.execute(
        db.select(Activity.activity_date)
        .where(
            Activity.user_id == user_id,
            Activity.challenge_id == challenge_id,
            Activity.activity_date >= week_start,
            Activity.activity_date <= week_end,
        )
        .group_by(Activity.activity_date)
        .having(func.sum(Activity.duration_minutes) >= 30)
    ).scalars().all()
    return len(result)


def _sick_days_in_week(user_id: int, challenge_id: int, week_start: date) -> int:
    """Count sick days that fall within the given week from SickPeriod records."""
    week_end = week_start + timedelta(days=6)
    periods = db.session.scalars(
        db.select(SickPeriod).where(
            SickPeriod.user_id == user_id,
            SickPeriod.challenge_id == challenge_id,
            SickPeriod.start_date <= week_end,
            SickPeriod.end_date >= week_start,
        )
    ).all()
    total = 0
    for p in periods:
        eff_start = max(p.start_date, week_start)
        eff_end = min(p.end_date, week_end)
        total += (eff_end - eff_start).days + 1
    return min(total, 7)


def calculate_weekly_penalty(
    user_id: int,
    challenge_id: int,
    week_start: date,
    weekly_goal: int,
    penalty_per_miss: float,
) -> float:
    """Calculate penalty for a single week."""
    # 1. Check SickPeriod overlap
    sick_days = _sick_days_in_week(user_id, challenge_id, week_start)
    if sick_days > 0:
        deductions = sick_days // 2
        effective_goal = max(0, weekly_goal - deductions)
        if effective_goal <= 0:
            return 0.0
        fulfilled = count_fulfilled_days(user_id, challenge_id, week_start)
        missed = max(0, effective_goal - fulfilled)
        return missed * penalty_per_miss

    # 2. Check PenaltyOverride
    override = db.session.execute(
        db.select(PenaltyOverride).where(
            PenaltyOverride.user_id == user_id,
            PenaltyOverride.challenge_id == challenge_id,
            PenaltyOverride.week_start == week_start,
        )
    ).scalar_one_or_none()
    if override is not None:
        return override.override_amount

    # 3. Count fulfilled days
    fulfilled = count_fulfilled_days(user_id, challenge_id, week_start)

    # 4. Missed days
    missed = max(0, weekly_goal - fulfilled)

    # 5. Penalty
    return missed * penalty_per_miss


def calculate_total_penalty(
    user_id: int,
    challenge: Challenge,
    participation: ChallengeParticipation,
) -> float:
    """Sum all weekly penalties for a participant."""
    today = date.today()
    mondays = get_week_mondays(challenge.start_date, challenge.end_date)

    total = 0.0
    for week_start in mondays:
        week_end = week_start + timedelta(days=6)

        # Only process weeks that have at least partially passed
        # For current/future weeks: only count up to yesterday's completed days
        if week_start > today:
            # Entirely future week — skip
            continue

        # Determine effective end of counting for this week
        effective_end = min(week_end, today - timedelta(days=1))

        # Determine how many goal days are possible in the elapsed portion
        elapsed_days = (effective_end - week_start).days + 1  # 1-7
        # Weekly goal days available: min(weekly_goal, elapsed_days)
        adjusted_goal = min(participation.weekly_goal, elapsed_days)

        if adjusted_goal <= 0:
            continue

        total += calculate_weekly_penalty(
            user_id=user_id,
            challenge_id=challenge.id,
            week_start=week_start,
            weekly_goal=adjusted_goal,
            penalty_per_miss=challenge.penalty_per_miss,
        )

    # Bailout fee
    if participation.status == "bailed_out":
        total += challenge.bailout_fee

    return total
