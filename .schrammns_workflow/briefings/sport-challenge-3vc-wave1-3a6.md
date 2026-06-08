# Briefing: I-01 – SickPeriod-Model + Alembic-Migration

**Mission:** SickWeek → SickPeriod Epic (sport-challenge-3vc)
**Your Task:** sport-challenge-3a6

## What to Do

Ersetze das wochenbasierte `SickWeek`-Modell durch ein datumsbasiertes `SickPeriod`-Modell.

### 1. Neues Model anlegen: `app/models/sick_period.py`

```python
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class SickPeriod(db.Model):
    __tablename__ = "sick_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
```

Kein UniqueConstraint (Overlap-Prüfung erfolgt in der Route).

### 2. Alembic-Migration erstellen

Führe `FLASK_APP=run.py flask db migrate -m "replace_sick_weeks_with_sick_periods"` aus (nach dem Anlegen des Models), dann bearbeite die generierte Migrationsdatei manuell.

Die Migration muss folgende Schritte enthalten:
- `op.create_table("sick_periods", ...)` mit allen Feldern
- Datenmigration: Für jede bestehende `sick_weeks`-Zeile eine `sick_periods`-Zeile einfügen:
  - `start_date = week_start`
  - `end_date = week_start + timedelta(days=max(sick_days, 1) - 1)` (geclampt auf 7 Tage)
- `op.drop_table("sick_weeks")`

**Downgrade** muss ebenfalls funktionieren (sick_periods → sick_weeks mit `sick_days = (end_date - start_date).days + 1`, geclampt auf 7).

**PFLICHT:** In der Migration-Datei `with op.batch_alter_table(...)` ODER `render_as_batch=True` nutzen. SQLite erfordert batch-Modus für Tabellen-Operationen. Die Migrations-Datei darf **nicht** automatisch generiert sein ohne manuelle Überprüfung – auto-generate erzeugt oft falsche Diffs für Uuid/Date-Spalten.

**WICHTIG:** Die Datenmigration mit `op.bulk_insert` oder via `connection.execute(text(...))` implementieren, nicht mit ORM-Klassen.

Beispiel für die Migration-Datei:
```python
from alembic import op
import sqlalchemy as sa
from datetime import date, timedelta

def upgrade():
    # 1. Neue Tabelle
    op.create_table(
        "sick_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("challenge_id", sa.Integer(), sa.ForeignKey("challenges.id"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # 2. Datenmigration
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT user_id, challenge_id, week_start, sick_days, created_at FROM sick_weeks")).fetchall()
    for row in rows:
        sick_days = max(row.sick_days or 7, 1)
        end_date = row.week_start + timedelta(days=min(sick_days, 7) - 1)
        conn.execute(sa.text(
            "INSERT INTO sick_periods (user_id, challenge_id, start_date, end_date, created_at) "
            "VALUES (:uid, :cid, :sd, :ed, :ca)"
        ), {"uid": row.user_id, "cid": row.challenge_id, "sd": row.week_start, "ed": end_date, "ca": row.created_at})
    
    # 3. Alte Tabelle löschen
    op.drop_table("sick_weeks")

def downgrade():
    op.create_table(
        "sick_weeks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("challenge_id", sa.Integer(), sa.ForeignKey("challenges.id"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("sick_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "challenge_id", "week_start"),
    )
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT user_id, challenge_id, start_date, end_date, created_at FROM sick_periods")).fetchall()
    for row in rows:
        sick_days = min((row.end_date - row.start_date).days + 1, 7)
        week_start = row.start_date - timedelta(days=row.start_date.weekday())
        conn.execute(sa.text(
            "INSERT OR IGNORE INTO sick_weeks (user_id, challenge_id, week_start, sick_days, created_at) "
            "VALUES (:uid, :cid, :ws, :sd, :ca)"
        ), {"uid": row.user_id, "cid": row.challenge_id, "ws": week_start, "sd": sick_days, "ca": row.created_at})
    op.drop_table("sick_periods")
```

### 3. `app/__init__.py` anpassen

Zeile 87: `from app.models.sick_week import SickWeek  # noqa: F401` ersetzen durch:
`from app.models.sick_period import SickPeriod  # noqa: F401`

### 4. `app/models/sick_week.py` löschen

Die Datei nach dem Anlegen der Migration und dem Model-Import-Update löschen.

## Verification

```bash
set -a && source .env && set +a
FLASK_APP=run.py .venv/bin/flask db upgrade
sqlite3 instance/app.db ".tables"    # muss sick_periods zeigen, KEIN sick_weeks
FLASK_APP=run.py .venv/bin/flask db downgrade -1   # smoke-test
FLASK_APP=run.py .venv/bin/flask db upgrade        # wieder upgraden
```

Wenn die App keine bestehende DB hat (Test-Umgebung), kann `flask db upgrade` aus leerem Zustand alles anlegen.

## File Ownership

- **WRITE:** `app/models/sick_period.py` (neu)
- **WRITE:** `migrations/versions/<auto-generated>.py` (neu)
- **WRITE:** `app/__init__.py` (L87)
- **DELETE:** `app/models/sick_week.py`

## Cross-Cutting Constraints

- `render_as_batch=True` in `migrations/env.py` ist bereits aktiv (Commit 21c5cfd) – nicht nötig, aber Migration selbst muss ohne `batch_alter_table` auskommen wenn kein ALTER TABLE gebraucht wird (hier: nur CREATE + DROP, kein ALTER)
- `end_date` immer NOT NULL
- SECRET_KEY aus .env: `set -a && source .env && set +a` vor flask-Befehlen
- Kein `bd edit` verwenden (blockiert Terminal)

## Result Format

```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/models/sick_period.py, app/__init__.py, migrations/versions/<id>_replace_sick_weeks_with_sick_periods.py
SUMMARY: SickPeriod-Model angelegt, Migration erstellt (Datenmigration + drop sick_weeks), __init__.py aktualisiert, sick_week.py gelöscht. flask db upgrade erfolgreich.
RESULT_END
```
