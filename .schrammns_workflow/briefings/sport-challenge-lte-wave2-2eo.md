# Briefing: 2.1 Strafberechnungs-Service

## Mission
Epic: Challenge-System — Implementierung des Strafberechnungs-Service.

## Your Task
Erstelle `app/services/__init__.py` (leer) und `app/services/penalty.py` mit der Strafberechnungs-Logik.

## Business Rules
1. Pro Woche muss ein Teilnehmer sein `weekly_goal` (2 oder 3) Tage mit ≥30 Min Gesamtdauer Sport erreichen
2. Mehrere Aktivitäten pro Tag werden summiert (2×20 Min = 40 Min → Tag zählt)
3. Pro verpasstem Tag: `challenge.penalty_per_miss` Euro Strafe (Standard: 5€)
4. Max Strafe pro Woche: `weekly_goal × penalty_per_miss` (z.B. 3×5€ = 15���)
5. Krankheitswoche (SickWeek existiert): 0€ Strafe für die ganze Woche
6. PenaltyOverride: Admin setzt fixen Betrag für eine Woche (überschreibt Berechnung)
7. Bailout: Gesamtstrafe + `challenge.bailout_fee` (Standard: 25€)
8. Wochen die noch nicht komplett vergangen sind (aktuelle/zukünftige): nur abgeschlossene Tage zählen

## Existing Models (already created in Wave 1)
```python
# app/models/challenge.py
class Challenge(db.Model):
    __tablename__ = "challenges"
    # id, name, start_date, end_date, penalty_per_miss (Float, default=5.0), bailout_fee (Float, default=25.0), created_by_id, created_at
    # participations = db.relationship("ChallengeParticipation", back_populates="challenge")

class ChallengeParticipation(db.Model):
    __tablename__ = "challenge_participations"
    # id, user_id, challenge_id, weekly_goal (Integer, default=3), status (String: invited/accepted/bailed_out)
    # invited_at, accepted_at, bailed_out_at

# app/models/activity.py
class Activity(db.Model):
    __tablename__ = "activities"
    # id, user_id, challenge_id, activity_date (Date), duration_minutes (Integer), sport_type, source, external_id, screenshot_path, created_at

# app/models/sick_week.py
class SickWeek(db.Model):
    __tablename__ = "sick_weeks"
    # UniqueConstraint("user_id", "challenge_id", "week_start")
    # id, user_id, challenge_id, week_start (Date = Monday), created_at

# app/models/penalty.py
class PenaltyOverride(db.Model):
    __tablename__ = "penalty_overrides"
    # UniqueConstraint("user_id", "challenge_id", "week_start")
    # id, user_id, challenge_id, week_start (Date), override_amount (Float), reason, set_by_id, created_at
```

## Database Access Pattern (from existing code)
```python
from app.extensions import db
# Query: db.session.execute(db.select(Model).where(...)).scalars().all()
# or: Model.query.filter_by(...).first()
```

## Deliverable

### File 1: `app/services/__init__.py` (NEW, empty)

### File 2: `app/services/penalty.py` (NEW)

Implement these functions:

```python
from datetime import date, timedelta
from sqlalchemy import func
from app.extensions import db
from app.models.activity import Activity
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.sick_week import SickWeek
from app.models.penalty import PenaltyOverride


def get_week_mondays(start_date: date, end_date: date) -> list[date]:
    """Returns all Mondays within the challenge period."""
    # Start from the Monday of start_date's week
    # Continue until end_date
    

def count_fulfilled_days(user_id: int, challenge_id: int, week_start: date) -> int:
    """Count days in the week where total duration >= 30 minutes.
    
    Query: SELECT activity_date, SUM(duration_minutes) 
    FROM activities 
    WHERE user_id=... AND challenge_id=... AND activity_date BETWEEN week_start AND week_start+6
    GROUP BY activity_date
    HAVING SUM(duration_minutes) >= 30
    
    Return the count of such days.
    """


def calculate_weekly_penalty(user_id: int, challenge_id: int, week_start: date, 
                              weekly_goal: int, penalty_per_miss: float) -> float:
    """Calculate penalty for a single week.
    
    1. Check SickWeek → return 0.0
    2. Check PenaltyOverride → return override_amount
    3. fulfilled = count_fulfilled_days(...)
    4. missed = max(0, weekly_goal - fulfilled)
    5. return missed * penalty_per_miss
    """


def calculate_total_penalty(user_id: int, challenge: Challenge, participation: ChallengeParticipation) -> float:
    """Sum all weekly penalties for a participant.
    
    Only count weeks up to today (not future weeks).
    If bailed_out: add challenge.bailout_fee.
    """
```

## File Ownership
- Create: `app/services/__init__.py` (NEW, empty), `app/services/penalty.py` (NEW)
- Do NOT modify any other files

## Verification
```bash
SECRET_KEY=test .venv/bin/python -c "from app.services.penalty import get_week_mondays, count_fulfilled_days, calculate_weekly_penalty, calculate_total_penalty; print('OK')"
```

## Output Format
```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/services/__init__.py, app/services/penalty.py
SUMMARY: Created penalty calculation service
RESULT_END
```
