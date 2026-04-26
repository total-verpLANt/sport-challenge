# Briefing: 1.4 BonusChallenge + BonusChallengeEntry Models

## Mission
Epic: Challenge-System — Implementierung des vollständigen Challenge-Systems.

## Your Task
Erstelle `app/models/bonus.py` mit BonusChallenge und BonusChallengeEntry Models.

## Cross-Cutting Constraints
- Nutze `from app.extensions import db` und `db.Model`
- Mapped columns mit Type Annotations
- UniqueConstraint für (user_id, bonus_challenge_id) auf BonusChallengeEntry

## Existing Pattern
```python
from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.extensions import db
```

## Deliverable

Create file `app/models/bonus.py`:

```python
class BonusChallenge(db.Model):
    __tablename__ = "bonus_challenges"
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="50 Squat Jumps")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

class BonusChallengeEntry(db.Model):
    __tablename__ = "bonus_challenge_entries"
    __table_args__ = (UniqueConstraint("user_id", "bonus_challenge_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    bonus_challenge_id: Mapped[int] = mapped_column(ForeignKey("bonus_challenges.id"), nullable=False)
    time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
```

## File Ownership
- ONLY modify: `app/models/bonus.py` (NEW)
- Do NOT modify any other files

## Verification
```bash
SECRET_KEY=test .venv/bin/python -c "from app.models.bonus import BonusChallenge, BonusChallengeEntry; print('OK')"
```

## Output Format
```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/models/bonus.py
SUMMARY: Created BonusChallenge and BonusChallengeEntry models
RESULT_END
```
