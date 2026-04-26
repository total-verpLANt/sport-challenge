# Briefing: 4.1 Weekly-Summary-Service

## Mission
Epic: Challenge-System — Wochen-Aggregation für Dashboard/Leaderboard.

## Your Task
Erstelle `app/services/weekly_summary.py` mit der Aggregations-Logik für das Dashboard.

## Business Rules
- Dashboard zeigt alle Teilnehmer über alle Wochen der Challenge
- Pro Woche: Anzahl erfüllter Tage (≥30 Min Gesamtdauer)
- "3+" bei Übererfüllung (mehr Tage als weekly_goal)
- Krankheitswochen markiert
- Strafstand pro Teilnehmer (Summe aller Wochen)
- Bailout-User sichtbar mit Gesamtkosten inkl. Gebühr

## Available Services & Models
```python
from app.services.penalty import get_week_mondays, count_fulfilled_days, calculate_weekly_penalty, calculate_total_penalty
# get_week_mondays(start_date, end_date) -> list[date]  (Mondays)
# count_fulfilled_days(user_id, challenge_id, week_start) -> int
# calculate_weekly_penalty(user_id, challenge_id, week_start, weekly_goal, penalty_per_miss) -> float
# calculate_total_penalty(user_id, challenge, participation) -> float

from app.models.challenge import Challenge, ChallengeParticipation
# Challenge: id, name, start_date, end_date, penalty_per_miss, bailout_fee, created_by_id
#   participations = relationship("ChallengeParticipation")
# ChallengeParticipation: id, user_id, challenge_id, weekly_goal, status, invited_at, accepted_at, bailed_out_at
#   user = relationship("User")

from app.models.sick_week import SickWeek
# SickWeek: user_id, challenge_id, week_start (Date)

from app.models.user import User
# User: id, email

from app.extensions import db
```

## Deliverable

### File: `app/services/weekly_summary.py` (NEW)

```python
from datetime import date
from app.extensions import db
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.sick_week import SickWeek
from app.services.penalty import get_week_mondays, count_fulfilled_days, calculate_total_penalty


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
                    },
                    ...
                },
                "total_penalty": float,
            },
            ...
        ]
    }
    
    Implementation:
    1. Get all participations with status in ("accepted", "bailed_out")
    2. Get all week mondays up to min(today, challenge.end_date)
    3. For each participant, for each week:
       - count_fulfilled_days()
       - Check if SickWeek exists
       - calculate_weekly_penalty()
    4. calculate_total_penalty() for grand total
    5. Sort participants by total_penalty ASC (least penalties first)
    """
```

The function should be efficient but correctness is more important than optimization at this stage.

## File Ownership
- Create: `app/services/weekly_summary.py` (NEW)
- Do NOT modify any other files

## Verification
```bash
SECRET_KEY=test .venv/bin/python -c "from app.services.weekly_summary import get_challenge_summary; print('OK')"
```

## Output Format
```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/services/weekly_summary.py
SUMMARY: Created weekly summary service for dashboard aggregation
RESULT_END
```
