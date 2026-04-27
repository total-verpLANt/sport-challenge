# Briefing: ffh.1 – ActivityMedia-Model + Alembic-Migration

**Epic:** Multimedia-Upload für Aktivitäten (sport-challenge-ffh)
**Issue:** sport-challenge-ffh.1
**Wave:** 1
**Risk:** irreversible / external / requires-approval (Migration bereits durch Plan-Approval genehmigt)

## Mission

Implementiere das `ActivityMedia`-ORM-Model und die Alembic-Migration für das Multimedia-Upload-Feature.

## Deine Aufgabe

### 1. app/models/activity.py erweitern

**Datei:** `/Users/schrammn/Documents/VSCodium/sport-challenge/app/models/activity.py`

Lies die Datei zuerst komplett. Dann:

a) Füge `ActivityMedia`-Klasse NACH der `Activity`-Klasse ein:

```python
class ActivityMedia(db.Model):
    __tablename__ = "activity_media"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), index=True
    )
    file_path: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(10))   # "image" | "video"
    original_filename: Mapped[str] = mapped_column(String(255))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    activity: Mapped["Activity"] = relationship(back_populates="media")
```

b) Füge auf der `Activity`-Klasse (nach dem `created_at`-Feld, also nach Zeile ~22) die Relation ein:

```python
    media: Mapped[list["ActivityMedia"]] = relationship(
        "ActivityMedia",
        back_populates="activity",
        cascade="all, delete-orphan",
        order_by="ActivityMedia.created_at",
    )
```

c) Ergänze Imports in `activity.py`:
- `Integer` zu den SQLAlchemy-Imports
- `relationship` zu den sqlalchemy.orm-Imports

### 2. Alembic-Migration erstellen

```bash
set -a && source .env && set +a
FLASK_APP=run.py .venv/bin/flask db migrate -m "add_activity_media_table"
```

Lies die generierte Migration in `migrations/versions/`. Prüfe ob sie korrekt ist.

Dann **editiere die Migration manuell** um:
- 3-Schritt-Struktur sicherzustellen
- Legacy-Datenmigration hinzuzufügen

Die `upgrade()`-Funktion soll so aussehen:

```python
def upgrade():
    # Schritt 1: Tabelle anlegen
    op.create_table(
        "activity_media",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("media_type", sa.String(length=10), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("activity_media", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_activity_media_activity_id"), ["activity_id"], unique=False)

    # Schritt 2: Legacy-Daten migrieren (screenshot_path → activity_media)
    op.execute("""
        INSERT INTO activity_media (activity_id, file_path, media_type, original_filename, file_size_bytes, created_at)
        SELECT id, screenshot_path, 'image', 'screenshot', 0, created_at
        FROM activities
        WHERE screenshot_path IS NOT NULL
    """)
    # Schritt 3: screenshot_path bleibt nullable – KEIN DROP in dieser Migration

def downgrade():
    with op.batch_alter_table("activity_media", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_activity_media_activity_id"))
    op.drop_table("activity_media")
```

**WICHTIG:** `render_as_batch=True` ist bereits in `migrations/env.py` gesetzt (Commit 21c5cfd).

### 3. Migration anwenden und testen

```bash
set -a && source .env && set +a
FLASK_APP=run.py .venv/bin/flask db upgrade
```

Prüfe:
```bash
set -a && source .env && set +a
.venv/bin/python -c "
from app import create_app
from app.models.activity import Activity, ActivityMedia
app = create_app()
with app.app_context():
    from app.extensions import db
    # Prüfe dass Relation funktioniert
    print('ActivityMedia importierbar:', ActivityMedia.__tablename__)
    print('Activity.media Relation:', Activity.media)
    print('OK')
"
```

## File Ownership

**Nur diese Dateien ändern:**
- `app/models/activity.py`
- `migrations/versions/<neu-generierte-hash>_add_activity_media_table.py`

**Nicht anfassen:**
- Alle anderen Dateien

## Acceptance Criteria

- [ ] `flask db upgrade` läuft ohne Fehler
- [ ] `ActivityMedia`-Klasse importierbar: `from app.models.activity import ActivityMedia`
- [ ] `activity.media` ist eine SQLAlchemy-Relation (list)
- [ ] Migration enthält Legacy-Datenmigration (INSERT INTO activity_media ... WHERE screenshot_path IS NOT NULL)
- [ ] `flask db downgrade` rollt Tabelle sauber zurück, dann `flask db upgrade` wieder hoch

## Boundaries (IMMER einhalten)

- `render_as_batch=True` in batch_alter_table (SQLite-Pflicht)
- `screenshot_path` auf Activity NICHT entfernen (bleibt nullable)
- Kein Committen – nur Code-Änderungen schreiben

## Output-Format

Antworte am Ende mit:

RESULT_START
STATUS: COMPLETE|BLOCKED|DESIGN_DECISION_REQUIRED
FILES_MODIFIED: app/models/activity.py, migrations/versions/<hash>_add_activity_media_table.py
SUMMARY: <1-2 Sätze was gemacht wurde>
BLOCKERS: <leer oder Beschreibung>
RESULT_END
