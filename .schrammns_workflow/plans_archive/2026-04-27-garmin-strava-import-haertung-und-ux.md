# Plan: Garmin/Strava-Import – Härtung und UX-Verbesserung

**Erstellt:** 2026-04-27
**Ziel:** Den bereits implementierten Garmin/Strava-Import sicher, duplikatfrei und gut erreichbar machen
**Research:** `.schrammns_workflow/research/2026-04-27-garmin-strava-import-challenge-aktivitaten.md`

---

## Executive Summary

Der Import-Flow (GET `import_form` + POST `import_submit`) ist vollständig implementiert
und funktionsfähig. Drei kritische Schwächen müssen vor dem produktiven Einsatz behoben werden:

1. **Kein UniqueConstraint auf `external_id`** → Duplikate bei Double-Submit möglich
2. **Kein Import-Einstiegspunkt in `my_week.html`** → Feature nicht auffindbar
3. **Index-basierte Zuordnung in `import_submit`** → falscher Datensatz bei Race-Condition
4. **Fehlende Tests** → kein Regressions-Schutz

---

## Baseline Audit (verifiziert 2026-04-27)

| Metrik | Wert | Befehl |
|--------|------|--------|
| Dateien zu ändern | 5 | `ls app/routes/challenge_activities.py app/models/activity.py ...` |
| Neue Dateien | 1 (Testdatei) | – |
| LOC in `challenge_activities.py` | 374 | `wc -l app/routes/challenge_activities.py` |
| LOC in `activity.py` | 26 | `wc -l app/models/activity.py` |
| Tests gesamt aktuell | 74 | `SECRET_KEY=testkey .venv/bin/pytest --collect-only -q` |
| Tests import-bezogen | 0 | `grep -c "import" tests/test_activities_log.py` |
| Migrationsstand | `cc5be1106ffa` | `ls migrations/versions/ | sort | tail -1` |

---

## Files to Modify

| File | Change |
|------|--------|
| `app/models/activity.py` | `UniqueConstraint("user_id", "external_id")` hinzufügen |
| `migrations/versions/NEW_add_external_id_unique.py` | **NEW** – Alembic-Migration für den UniqueConstraint |
| `app/routes/challenge_activities.py` | `import_submit`: index-basierte Zuordnung → external_id-basiert; IntegrityError-Handling |
| `app/templates/activities/my_week.html` | Import-Button hinzufügen |
| `app/templates/activities/import.html` | Formular sendet `external_id` statt `idx` als Checkbox-Value |
| `tests/test_import.py` | **NEW** – Tests für import_form, import_submit, Duplikat-Schutz |

---

## Implementation Detail

### Issue 1: UniqueConstraint auf `external_id`

**Datei:** `app/models/activity.py`

Aktuell:
```python
class Activity(db.Model):
    __tablename__ = "activities"
    # ... Felder ohne __table_args__
```

Neu – `__table_args__` ergänzen:
```python
from sqlalchemy import UniqueConstraint

class Activity(db.Model):
    __tablename__ = "activities"
    # ... alle Felder unverändert ...
    __table_args__ = (
        UniqueConstraint("user_id", "external_id", name="uq_activity_user_external"),
    )
```

**Wichtig:** `NULL`-Werte in SQLite sind nicht unique (mehrere manuelle Aktivitäten mit `external_id=None` sind erlaubt) – das ist korrekt.

**Migration generieren:**
```bash
FLASK_APP=run.py SECRET_KEY=testkey .venv/bin/flask db migrate \
  -m "add unique constraint user_id external_id to activities"
```

Die generierte Migration prüfen – sie muss `render_as_batch=True` nutzen (bereits in `env.py` konfiguriert).

**Acceptance Criteria:**
- `Activity.__table_args__` enthält `UniqueConstraint("user_id", "external_id")`
- Migration existiert und ist gültig (`flask db upgrade` läuft durch)
- Zweites Einfügen derselben `external_id` für denselben User wirft `IntegrityError`

---

### Issue 2: Import-Submit – external_id-basierte Zuordnung

**Datei:** `app/routes/challenge_activities.py`

**Problem:** `import_submit` liest `request.form.getlist("selected")` als Array-Indizes und indexiert damit `raw[idx]`. Wenn zwischen GET und POST eine neue Aktivität sync'd, kann ein falscher Datensatz importiert werden.

**Lösung:** Checkbox-Value = `external_id` statt `idx`. `import_submit` sucht die Aktivität via `external_id` in der frisch geholten Liste.

**Template-Änderung** (`app/templates/activities/import.html`):
```html
<!-- Alt: -->
<input type="checkbox" name="selected" value="{{ act.idx }}" ...>

<!-- Neu: -->
<input type="checkbox" name="selected" value="{{ act.external_id }}" ...>
```

**Route-Änderung** (`app/routes/challenge_activities.py`, Funktion `import_submit`):
```python
# Alt (Zeilen ~330-355):
selected_indices = request.form.getlist("selected")
for idx_str in selected_indices:
    idx = int(idx_str)
    act = raw[idx]
    ext_id = f"{provider_type}:{act['startTimeLocal']}"
    # ...

# Neu:
from sqlalchemy.exc import IntegrityError

selected_ext_ids = request.form.getlist("selected")
# raw_by_ext_id: Lookup-Dict für O(1)-Zugriff
raw_by_ext_id = {
    f"{provider_type}:{a['startTimeLocal']}": a for a in raw
}
imported = 0
for ext_id in selected_ext_ids:
    act = raw_by_ext_id.get(ext_id)
    if act is None:
        continue  # nicht mehr in der Liste (zu alter Offset?)
    try:
        activity = Activity(
            user_id=current_user.id,
            challenge_id=participation.challenge_id,
            activity_date=date.fromisoformat(act["startTimeLocal"][:10]),
            duration_minutes=max(1, int(act["duration"]) // 60),
            sport_type=act.get("activityType", {}).get("typeKey", "unknown"),
            source=provider_type,
            external_id=ext_id,
        )
        db.session.add(activity)
        db.session.commit()
        imported += 1
    except IntegrityError:
        db.session.rollback()
        # Duplikat – bereits importiert, kein Fehler anzeigen
```

**Import ergänzen** (falls nicht vorhanden):
```python
from sqlalchemy.exc import IntegrityError
```

**Acceptance Criteria:**
- Checkbox-Value im Template ist `external_id` (String, nicht Integer)
- Double-Submit derselben Aktivität importiert sie genau einmal
- Aktivität, die zwischen GET und POST verschwunden ist, wird übersprungen (kein 500er)
- `IntegrityError` wird per Rollback behandelt, kein Crash

---

### Issue 3: Import-Button in my_week.html

**Datei:** `app/templates/activities/my_week.html`

Aktuell (Zeile 6):
```html
<a href="{{ url_for('challenge_activities.log_form') }}" class="btn btn-primary btn-sm">
  + Aktivität eintragen
</a>
```

Ergänzen (nach dem vorhandenen Button):
```html
{% if has_connector %}
<a href="{{ url_for('challenge_activities.import_form') }}" class="btn btn-outline-secondary btn-sm">
  ↓ Aus Garmin/Strava importieren
</a>
{% endif %}
```

**Context-Variable `has_connector`** im `my_week`-View ergänzen:
```python
# In app/routes/challenge_activities.py, Funktion my_week():
from app.models.connector import ConnectorCredential
has_connector = ConnectorCredential.query.filter_by(
    user_id=current_user.id
).first() is not None
return render_template(..., has_connector=has_connector)
```

**Acceptance Criteria:**
- Import-Button erscheint in `my_week.html` wenn User einen Connector verbunden hat
- Button fehlt wenn kein Connector verbunden
- Klick auf Button navigiert zu `GET /challenge-activities/import`

---

### Issue 4: Tests für Import-Flow

**Datei:** `tests/test_import.py` (neu)

Nutze vorhandenes Pattern aus `tests/test_activities_log.py` (conftest, client, db-Fixture).

**Test-Funktionen:**

```python
tests/test_import.py — neu anlegen:

- test_import_form_redirects_without_connector:
    GET /import ohne ConnectorCredential → Redirect zu /connectors/

- test_import_form_redirects_without_participation:
    GET /import ohne aktive Participation → Redirect zu /challenges/

- test_import_form_shows_activities_with_mock_connector:
    GET /import mit gemocktem get_activities() → 200, Aktivitäten in HTML

- test_import_form_marks_already_imported:
    Activity mit external_id in DB → Template zeigt "Bereits importiert"

- test_import_submit_creates_activity:
    POST /import mit selected=[ext_id] → Activity in DB mit source="garmin"

- test_import_submit_skips_duplicate:
    POST /import zweimal mit gleicher ext_id → nur 1 Activity in DB

- test_import_submit_handles_missing_ext_id:
    POST /import mit ext_id die nicht in raw ist → kein Crash, 0 importiert
```

**Mock-Strategie:** `unittest.mock.patch` auf `GarminConnector.connect` und `GarminConnector.get_activities` (gibt Liste von Test-Dicts zurück). Keine echte Garmin-API in Tests.

**Acceptance Criteria:**
- `pytest tests/test_import.py -v` läuft durch (7 neue Tests)
- Gesamtanzahl Tests: ≥ 81 (74 + 7)

---

## Design Decisions

| Decision | Chosen | Rejected | Rationale |
|----------|--------|----------|-----------|
| Deduplizierung | `IntegrityError` fangen (DB-Constraint) | Nur Laufzeit-Query | DB-Constraint ist atomare Sperre; Race-Condition-sicher |
| Checkbox-Value | `external_id` (String) | Array-Index (int) | Index-Zuordnung fragil bei parallelen Requests/Refresh |
| Import-Button Sichtbarkeit | Nur wenn Connector vorhanden (`has_connector`) | Immer sichtbar | Verwirrung vermeiden wenn kein Connector verbunden |
| Test-Mock-Ebene | Connector-Methoden mocken | HTTP-Layer | Schneller, isoliert, kein Netzwerk |

---

## Waves

### Wave 1 (parallel ausführbar)

| Issue | Titel | Dateien | Risiko |
|-------|-------|---------|--------|
| I-01 | UniqueConstraint + Migration | `activity.py`, `migrations/` | `irreversible / external / requires-human` (Migration) |
| I-02 | my_week.html Import-Button | `my_week.html`, `challenge_activities.py` (my_week-View) | `reversible / local / autonomous-ok` |

> **I-01 requires-human:** Migration ändert DB-Schema irreversibel. Käpt'n muss Backup machen und Migration manuell approven.

### Wave 2 (nach Wave 1)

| Issue | Titel | Dateien | Abhängigkeit | Risiko |
|-------|-------|---------|-------------|--------|
| I-03 | external_id-basierter Submit | `challenge_activities.py`, `import.html` | I-01 (IntegrityError-Handling setzt UniqueConstraint voraus) | `reversible / system / autonomous-ok` |

### Wave 3 (nach Wave 2)

| Issue | Titel | Dateien | Abhängigkeit | Risiko |
|-------|-------|---------|-------------|--------|
| I-04 | Tests für Import-Flow | `tests/test_import.py` (neu) | I-03 (Tests testen finalen Code) | `reversible / local / autonomous-ok` |

---

## Boundaries

**Always:**
- Jeder Fix atomar: ein Issue = ein Commit
- Vor Migration: SQLite-Backup
- `IntegrityError` immer per `db.session.rollback()` behandeln
- `render_as_batch=True` ist bereits in `migrations/env.py` konfiguriert – kein Anpassungsbedarf

**Never:**
- Keine externen Garmin/Strava-API-Calls in Tests (immer mocken)
- Keine Änderung an `Activity`-Felder außer `__table_args__`
- Kein Entfernen des `idx`-Feldes aus der Template-Context-Variable (wird ggf. für andere Zwecke genutzt)

**Ask First:** (keine – alle Entscheidungen oben dokumentiert)

---

## Rollback-Strategie

| Wave | Rollback |
|------|---------|
| Pre-Start | `git tag pre-import-hardening` |
| I-01 | `flask db downgrade cc5be1106ffa` + `git revert` |
| I-02 | `git revert` (nur Template) |
| I-03 | `git revert` |
| I-04 | `git revert` (nur Testdatei) |

---

## Invalidation Risks

| Annahme | Risiko | Betroffene Issues |
|---------|--------|-------------------|
| `render_as_batch=True` in env.py konfiguriert | Niedrig – in Wachwechsel #8 bestätigt | I-01 |
| `startTimeLocal` ist immer `"YYYY-MM-DD HH:MM:SS"` | Mittel – Garmin/Strava könnten Timezone-Suffix liefern | I-03 |
| `credentials[0]` ist immer ein bekannter Provider | Niedrig – PROVIDER_REGISTRY enthält nur garmin+strava | I-02, I-03 |

---

## Verification Commands

```bash
# Nach I-01:
SECRET_KEY=testkey FLASK_APP=run.py .venv/bin/flask db upgrade
SECRET_KEY=testkey .venv/bin/pytest -q  # 74 Tests müssen grün bleiben

# Nach I-02:
# Playwright-Check: my_week zeigt Import-Button bei verbundenem Connector

# Nach I-03:
SECRET_KEY=testkey .venv/bin/pytest -q  # 74+ Tests grün

# Nach I-04:
SECRET_KEY=testkey .venv/bin/pytest tests/test_import.py -v
SECRET_KEY=testkey .venv/bin/pytest -q  # ≥ 81 Tests grün
```
