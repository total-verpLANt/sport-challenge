# Briefing: 1.3 SickWeek + PenaltyOverride Models

## Mission
Epic: Challenge-System — Implementierung des vollständigen Challenge-Systems.

## Your Task
Erstelle zwei neue Model-Dateien: `app/models/sick_week.py` und `app/models/penalty.py`.

## Cross-Cutting Constraints
- Nutze `from app.extensions import db` und `db.Model`
- Mapped columns mit Type Annotations (`Mapped[type]` + `mapped_column(...)`)
- DateTime-Felder mit `timezone=True`

## Existing Pattern (from app/models/connector.py)
```python
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.extensions import db
```

## Deliverable

### File 1: `app/models/sick_week.py`
```python
class SickWeek(db.Model):
    __tablename__ = "sick_weeks"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id", "week_start"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)  # Monday of the week
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
```

### File 2: `app/models/penalty.py`
```python
class PenaltyOverride(db.Model):
    __tablename__ = "penalty_overrides"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id", "week_start"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)  # Monday of the week
    override_amount: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    set_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
```

Note: Import `Date` from sqlalchemy and `date` from datetime module.

## File Ownership
- ONLY modify: `app/models/sick_week.py` (NEW), `app/models/penalty.py` (NEW)
- Do NOT modify any other files

## Verification
```bash
SECRET_KEY=test .venv/bin/python -c "from app.models.sick_week import SickWeek; from app.models.penalty import PenaltyOverride; print('OK')"
```

## Output Format
```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/models/sick_week.py, app/models/penalty.py
SUMMARY: Created SickWeek and PenaltyOverride models
RESULT_END
```
