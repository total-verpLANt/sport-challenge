# Research: UUID public_id + is_public Visibility + Alembic SQLite Migration

**Date:** 2026-04-27
**Scope:** Flask/SQLAlchemy UUID-as-slug Pattern, is_public Flag, Alembic SQLite 3-Step Migration

---

## Executive Summary

- **Integer PK behalten, `public_id` (UUID) ergänzen** ist der richtige Ansatz: alle FK-Joins laufen weiterhin über Int, nur URLs exponieren die UUID. Das ist der SQLAlchemy/Flask-Industriestandard für bestehende Tabellen mit Daten.
- **6 Routen** in `challenges.py` verwenden `<int:challenge_id>` und müssen auf `<string:public_id>` umgestellt werden. Die `challenge_activities`-Routes sind **nicht betroffen** (leiten challenge_id intern über die Participation her).
- **SQLite-Migration ist machbar**, erfordert aber zwingend `batch_alter_table` + einen 3-Schritt-Prozess (nullable → UPDATE → NOT NULL).
- **`render_as_batch=True`** fehlt noch in `migrations/env.py` – das muss als Teil dieser Arbeit ergänzt werden, sonst bricht die Migration.
- **`default=uuid.uuid4`** (Python-seitig, kein `server_default`) ist Pflicht: SQLite kennt keine UUID-Generierungsfunktion.
- Der **SQLAlchemy 2.0 `Uuid`-Typ** ist database-agnostisch und speichert auf SQLite als `CHAR(32)` (hex, ohne Bindestriche).

---

## Key Files

| File | Purpose |
|------|---------|
| `app/models/challenge.py` | Challenge + ChallengeParticipation Models – hier kommen `public_id` und `is_public` rein |
| `app/routes/challenges.py` | Alle 6 Challenge-Routen mit `<int:challenge_id>` – vollständige Umstellung nötig |
| `app/templates/challenges/index.html` | 4 url_for-Aufrufe mit challenge_id |
| `app/templates/challenges/detail.html` | 5 url_for-Aufrufe mit challenge_id |
| `app/templates/challenges/create.html` | Formular – is_public Toggle ergänzen |
| `migrations/env.py` | render_as_batch=True fehlt |
| `migrations/versions/77fe1b237497_*.py` | Neueste Migration, Pattern-Vorlage für batch_alter_table |
| `tests/test_challenge.py` | 6 Tests mit Integer-ID-URLs – müssen auf public_id umgestellt werden |

---

## Technology Stack

| Library/Framework | Version (if known) | Role |
|-------------------|--------------------|------|
| Flask-SQLAlchemy | 3.x | ORM, Typed Mapped Columns |
| Alembic | 1.x | Migrationstool |
| SQLite | via Python stdlib | Dev-DB |
| SQLAlchemy `Uuid` | SQLAlchemy 2.0+ | Database-agnostischer UUID-Typ |

---

## Findings

### F-1: UUID-as-PK vs. Integer PK + `public_id`

**Empfehlung: Integer PK behalten + `public_id` ergänzen.**

Gründe:
- Alle bestehenden FK-Referenzen (`ChallengeParticipation.challenge_id`, `Activity.challenge_id`, etc.) bleiben unverändert
- Join-Performance bleibt bei Int (4 Byte) vs. UUID (16 Byte / 32 Zeichen)
- Kein Kaskaden-Change durch alle 5 referenzierenden Models nötig
- Bei bestehenden Daten: kein PK-Tausch, der FK-Constraints kurzzeitig verletzt

SQLAlchemy 2.0 `Uuid`-Typ (database-agnostisch):
```python
from sqlalchemy.types import Uuid
public_id: Mapped[uuid.UUID] = mapped_column(
    Uuid, default=uuid.uuid4, nullable=False, unique=True, index=True
)
```
- PostgreSQL: nativer `UUID`-Typ
- SQLite: `CHAR(32)` (hex-String)
- Python: automatische `uuid.UUID`-Objekt-Konvertierung

**Wichtig:** `default=uuid.uuid4` (Callable, kein Aufruf!), **nicht** `server_default` – SQLite hat keine UUID-Funktion.

### F-2: Alembic SQLite Migration – 3-Schritt Pattern

SQLite unterstützt kein `ADD COLUMN … NOT NULL` ohne DEFAULT. Etabliertes Pattern:

```python
def upgrade():
    # Schritt 1: Nullable hinzufügen
    with op.batch_alter_table("challenges", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("public_id", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("is_public", sa.Boolean(), nullable=True))

    # Schritt 2: Bestehende Rows befüllen
    conn = op.get_bind()
    import uuid as _uuid
    rows = conn.execute(sa.text("SELECT id FROM challenges")).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE challenges SET public_id = :uid, is_public = 0 WHERE id = :id"),
            {"uid": _uuid.uuid4().hex, "id": row.id}
        )

    # Schritt 3: NOT NULL + UNIQUE setzen
    with op.batch_alter_table("challenges", recreate="auto") as batch_op:
        batch_op.alter_column("public_id", nullable=False, existing_type=sa.String(32))
        batch_op.alter_column("is_public", nullable=False, existing_type=sa.Boolean())
        batch_op.create_unique_constraint("uq_challenges_public_id", ["public_id"])
```

**`render_as_batch=True` fehlt in `migrations/env.py`** – muss vor der Migration ergänzt werden:
```python
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    render_as_batch=True,  # PFLICHT für SQLite ALTER TABLE
)
```

Dieses Flag fehlt bisher und ist der einzige Grund, warum die bisherigen Migrations händisch `batch_alter_table` genutzt haben (statt es autogeneriert zu bekommen).

### F-3: Betroffene Routen – Vollständige Liste

**Nur `challenges.py` – 6 Routen betroffen:**

| Route | Änderung |
|-------|----------|
| `GET /<int:challenge_id>` → `GET /<string:public_id>` | `db.session.get(Challenge, id)` → `Challenge.query.filter_by(public_id=...).first_or_404()` |
| `POST /<int:challenge_id>/invite` | gleiche Umstellung |
| `POST /<int:challenge_id>/accept` | gleiche Umstellung |
| `POST /<int:challenge_id>/decline` | gleiche Umstellung |
| `POST /<int:challenge_id>/bailout` | gleiche Umstellung |
| `POST /<int:challenge_id>/sick` | gleiche Umstellung |

**Nicht betroffen:**
- `challenge_activities.py` – kein `challenge_id` in der URL (wird über `_active_participation()` abgeleitet)
- `bonus.py` – verwendet `active_challenge.id` intern, nicht in URL
- `dashboard.py` – kein challenge_id in URL

### F-4: URL-Generierung in Templates – Vollständige Liste

**challenges/index.html:**
- Zeile 23: `accept`-Formularaction mit `pending_invitation.challenge_id`
- Zeile 36: `decline`-Formularaction
- Zeile 58: Detail-Link mit `active_challenge.id`
- Zeile 70: Admin-Detail-Link mit `any_active_challenge.id`

**challenges/detail.html:**
- Zeilen 49, 62, 78, 82, 106: Formularactions (accept, decline, sick, bailout, invite)

**Umstellung:** alle `challenge_id=challenge.id` → `public_id=challenge.public_id`
Im Template wird `challenge.public_id` automatisch als String rendered (SQLAlchemy `Uuid` → `str(uuid_obj)` → `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`).

### F-5: Sichtbarkeits-Logik (is_public + Übersicht)

**`detail`-Route – neue Autorisierungslogik:**
```python
# is_public=True: alle eingeloggten User dürfen sehen
# is_public=False: nur Teilnehmer oder Admin
if not challenge.is_public and not current_user.is_admin:
    participation = ...query for current user...
    if participation is None:
        abort(403)
```

**`index`-Route – alle sichtbaren Challenges:**
```python
# Alle Challenges, die der User sehen darf:
# 1. Challenges, an denen er teilnimmt (alle Status)
# 2. Alle öffentlichen Challenges
my_challenge_ids = db.session.scalars(
    db.select(ChallengeParticipation.challenge_id)
    .where(ChallengeParticipation.user_id == current_user.id)
).all()
visible_challenges = db.session.scalars(
    db.select(Challenge).where(
        db.or_(Challenge.id.in_(my_challenge_ids), Challenge.is_public == True)
    ).order_by(Challenge.created_at.desc())
).all()
```

### F-6: Test-Anpassungen

**`test_challenge.py`:** 6 Tests nutzen `f"/challenges/{challenge.id}/..."` → auf `f"/challenges/{challenge.public_id}/..."` umstellen.
Da `challenge.public_id` ein `uuid.UUID`-Objekt ist, liefert `str(challenge.public_id)` den URL-kompatiblen String.

**conftest.py:** Challenge-Factory-Fixture muss kein `public_id` setzen – wird automatisch via `default=uuid.uuid4` befüllt.

---

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| UUID-as-PK vs. public_id Pattern | 4 | SQLAlchemy 2.0 Uuid-Typ verifiziert via Context7 |
| Alembic SQLite 3-Schritt Migration | 4 | Pattern aus bestehenden Migrations verifiziert |
| Betroffene Routen + Templates | 4 | Alle Dateien vollständig gelesen |
| is_public Sichtbarkeitslogik | 3 | Logik klar, Implementierungsdetails noch offen |
| Test-Anpassungen | 3 | Dateinamen + Muster identifiziert |
| render_as_batch in env.py | 4 | Fehler in env.py verifiziert, Fix bekannt |

---

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Soll `is_public` auch Nicht-eingeloggte erlauben? | must-fill | Kapitän entscheidet |
| Soll die Challenge-Übersicht paginiert werden? | nice-to-have | Klären wenn viele Challenges erwartet |
| `bonus.py` – soll auch `bonus_id` aus der URL verschwinden? | nice-to-have | Separates Ticket nach diesem Feature |

---

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| Integer PK bleibt als Primary Key | Yes | Bestehende FK-Referenzen in 5 Models |
| `challenge_activities` braucht keine URL-Änderung | Yes | `challenge_activities.py` – kein challenge_id in Route-Dekorern |
| SQLAlchemy `Uuid`-Typ auf SQLite = CHAR(32) | Yes | SQLAlchemy 2.0 Docs via Context7 |
| `render_as_batch=True` fehlt in env.py | Yes | `migrations/env.py` gelesen – kein Flag vorhanden |
| `default=uuid.uuid4` reicht für auto-Befüllung | Yes | Bestehende Patterns + SQLAlchemy Docs |
| `str(challenge.public_id)` liefert URL-kompatiblen String | Yes | Python uuid.UUID.__str__ = Bindestriche-Form |

---

## Recommendations

1. **`render_as_batch=True`** zu `migrations/env.py` hinzufügen – als eigenständigen ersten Commit, da er alle zukünftigen SQLite-Migrations betrifft.
2. Migration im **3-Schritt-Pattern** schreiben (nullable → UPDATE → NOT NULL), nicht via `flask db migrate` autogenerieren.
3. **`sqlalchemy.types.Uuid`** verwenden (nicht `sa.String(36)` + manuelle Konvertierung).
4. **URL-Konverter**: Flask's eingebauter `<uuid:...>`-Converter kann genutzt werden, wenn `str(uuid_obj)` (mit Bindestrichen) in der URL steht. Alternativ `<string:public_id>` + `uuid.UUID(public_id)` im Handler.
5. **`is_public`-Scope**: Entscheidung treffen ob öffentliche Challenges auch Nicht-eingeloggte sehen dürfen (Klärung vor Implementierung nötig).
6. **Tests**: `public_id`-Attribute werden von der Fixture automatisch befüllt – nur URL-Strings in f-Ausdrücken anpassen.
