# Briefing: 1.1 Challenge + Participation Models

## Mission
Epic: Challenge-System — Implementierung des vollständigen Challenge-Systems.

## Your Task
Erstelle `app/models/challenge.py` mit zwei SQLAlchemy Models: `Challenge` und `ChallengeParticipation`.

## Cross-Cutting Constraints
- Alle Models nutzen `from app.extensions import db` und `db.Model`
- Mapped columns mit Type Annotations (`Mapped[type]` + `mapped_column(...)`)
- DateTime-Felder mit `timezone=True` und `default=lambda: datetime.now(timezone.utc)`
- Imports konsistent mit bestehenden Models (siehe Patterns unten)

## Existing Pattern (from app/models/user.py)
```python
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.extensions import db
```

## Deliverable

Create file `app/models/challenge.py` with:

### Challenge Model
```python
class Challenge(db.Model):
    __tablename__ = "challenges"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    penalty_per_miss: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    bailout_fee: Mapped[float] = mapped_column(Float, nullable=False, default=25.0)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
    participations = db.relationship("ChallengeParticipation", back_populates="challenge")
```

### ChallengeParticipation Model
```python
class ChallengeParticipation(db.Model):
    __tablename__ = "challenge_participations"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    weekly_goal: Mapped[int] = mapped_column(Integer, nullable=False, default=3)  # 2 or 3
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="invited")
        # Values: invited, accepted, bailed_out
    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bailed_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    challenge = db.relationship("Challenge", back_populates="participations")
    user = db.relationship("User")
```

## File Ownership
- ONLY modify: `app/models/challenge.py` (NEW)
- Do NOT modify any other files

## Verification
After creating the file, verify it imports cleanly:
```bash
SECRET_KEY=test .venv/bin/python -c "from app.models.challenge import Challenge, ChallengeParticipation; print('OK')"
```

## Output Format
When done, output exactly:
```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/models/challenge.py
SUMMARY: Created Challenge and ChallengeParticipation models
RESULT_END
```
If blocked, use STATUS: BLOCKED with BLOCKERS field.
