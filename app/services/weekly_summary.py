from datetime import date

from app.extensions import db
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.sick_week import SickWeek
from app.services.penalty import (
    get_week_mondays,
    count_fulfilled_days,
    calculate_weekly_penalty,
    calculate_total_penalty,
)


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

    # 3. Pre-fetch all SickWeeks for this challenge in one query
    sick_weeks_rows = db.session.execute(
        db.select(SickWeek).where(SickWeek.challenge_id == challenge.id)
    ).scalars().all()
    # Index: (user_id, week_start) -> True
    sick_index: set[tuple[int, date]] = {
        (sw.user_id, sw.week_start) for sw in sick_weeks_rows
    }

    # 4. Build per-participant data
    participants_data = []
    for participation in participations:
        user = participation.user
        weekly_goal = participation.weekly_goal

        weeks_data: dict[date, dict] = {}
        for week_start in weeks:
            fulfilled_days = count_fulfilled_days(user.id, challenge.id, week_start)
            is_sick = (user.id, week_start) in sick_index

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
