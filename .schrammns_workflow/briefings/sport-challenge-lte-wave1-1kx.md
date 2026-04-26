# Briefing: 1.2 Activity Model

## Mission
Epic: Challenge-System — Implementierung des vollständigen Challenge-Systems.

## Your Task
Erstelle `app/models/activity.py` mit dem Activity Model für manuelle und importierte Aktivitäts-Einträge.

## Cross-Cutting Constraints
- Nutze `from app.extensions import db` und `db.Model`
- Mapped columns mit Type Annotations (`Mapped[type]` + `mapped_column(...)`)
- DateTime-Felder mit `timezone=True` und `default=lambda: datetime.now(timezone.utc)`

## Existing Pattern (from app/models/user.py)
```python
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.extensions import db
```

## Deliverable

Create file `app/models/activity.py` with:

```python
class Activity(db.Model):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    sport_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
        # Values: manual, garmin, strava
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
```

Note: `activity_date` uses `date` (not `datetime`) — import from `datetime` module. Use `Date` from sqlalchemy.

## File Ownership
- ONLY modify: `app/models/activity.py` (NEW)
- Do NOT modify any other files

## Verification
```bash
SECRET_KEY=test .venv/bin/python -c "from app.models.activity import Activity; print('OK')"
```

## Output Format
```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/models/activity.py
SUMMARY: Created Activity model with manual/import fields
RESULT_END
```
