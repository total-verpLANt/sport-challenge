from collections import defaultdict
from datetime import date, timedelta

from app.extensions import db
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.sick_period import SickPeriod
from app.services.penalty import (
    get_week_mondays,
    count_fulfilled_days,
    calculate_weekly_penalty,
    calculate_total_penalty,
)


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
        )
        .scalars()
        .all()
    )

    # 3. Pre-fetch all SickPeriods for this challenge in one query
    all_sick_periods = db.session.scalars(
        db.select(SickPeriod).where(SickPeriod.challenge_id == challenge.id)
    ).all()
    # Group by user_id for O(1) lookup per user
    sick_by_user: dict[int, list] = defaultdict(list)
    for sp in all_sick_periods:
        sick_by_user[sp.user_id].append(sp)

    # 4. Build per-participant data
    participants_data = []
    for participation in participations:
        user = participation.user
        weekly_goal = participation.weekly_goal

        weeks_data: dict[date, dict] = {}
        for week_start in weeks:
            fulfilled_days = count_fulfilled_days(user.id, challenge.id, week_start)
            sick_days_val = _sick_days_from_periods(sick_by_user[user.id], week_start)
            is_sick = sick_days_val > 0

            penalty = calculate_weekly_penalty(
                user_id=user.id,
                challenge_id=challenge.id,
                week_start=week_start,
                weekly_goal=weekly_goal,
                penalty_per_miss=challenge.penalty_per_miss,
            )

            weeks_data[week_start] = {
                "fulfilled_days": fulfilled_days,
                "is_sick": is_sick,
                "sick_days": sick_days_val,
                "penalty": penalty,
                # "3+" indicator: participant exceeded weekly goal
                "overachieved": fulfilled_days > weekly_goal,
            }

        total_penalty = calculate_total_penalty(user.id, challenge, participation)

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
