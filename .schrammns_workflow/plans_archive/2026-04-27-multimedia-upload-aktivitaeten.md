# Plan: Multimedia-Upload für Aktivitäten

**Datum:** 2026-04-27
**Basis:** Research `.schrammns_workflow/research/2026-04-27-multimedia-upload-aktivitaeten.md`
**Epic:** Mehrere Fotos + Videos pro Aktivität, Drag-n-Drop, Medien-Anzeige, nachträglicher Upload

---

## Executive Summary

Das aktuelle System erlaubt exakt **einen** Screenshot pro Aktivität (1:1-Feld `screenshot_path`).
Das Feature ersetzt dieses durch eine neue **`ActivityMedia`-Tabelle** (1:n), erweitert `uploads.py`
um Video-Typen, baut ein Drag-n-Drop-Formular (Vanilla JS) und fügt eine Route für nachträglichen
Upload hinzu. `MAX_CONTENT_LENGTH` wird global auf 50 MB erhöht.

---

## Entscheidungen (vom Kapitän getroffen)

| Entscheidung | Wert | Rationale |
|-------------|------|-----------|
| Video-Größenlimit | 50 MB (global `MAX_CONTENT_LENGTH`) | Sport-Clips 1–2 Min. passen rein |
| Drag-n-Drop | Vanilla JS, kein Dropzone.js | Kein npm-Dependency, ~50 Zeilen |
| Legacy-Feld | `screenshot_path` bleibt nullable | Rollback möglich, keine Datenverlust-Migration |
| DB-Approach | Neue `ActivityMedia`-Tabelle (1:n) | Sauber, erweiterbar, kein Array-Feld |

---

## Baseline (verifiziert)

| Metrik | Wert | Befehl |
|--------|------|--------|
| Files to modify | 10 | `wc -l` oben |
| Test-Count (activities) | 7 | `grep -c "^def test_" tests/test_activities_log.py` |
| Upload-Tests | 0 | `grep -L "save_upload\|BytesIO" tests/` |
| `screenshot_path`-Referenzen | 18 | `grep -rn "screenshot_path"` |
| Bestehende Migrations | 9 | `ls migrations/versions/` |
| LOC gesamt betroffene Files | 1050 | `wc -l` |

---

## Files to Modify

| File | Änderung |
|------|---------|
| `app/models/activity.py` | `ActivityMedia`-Klasse + `media`-Relation auf `Activity` |
| `app/utils/uploads.py` | Video-Extensions, `get_media_type()`, `delete_media_files()` |
| `config.py` | `MAX_CONTENT_LENGTH` 5 MB → 50 MB |
| `app/routes/challenge_activities.py` | `log_submit` auf `getlist()`, `delete_activity` löscht `ActivityMedia`, neue Route `add_media` |
| `app/templates/activities/log.html` | Drag-n-Drop Zone (Vanilla JS), `multiple`, Video-Accept |
| `app/templates/activities/detail.html` | Media-Gallery + `<video>`-Tag + "Medien hinzufügen"-Button |
| `app/templates/activities/my_week.html` | Mediavorschau aus `ActivityMedia` statt `screenshot_path` |
| `app/templates/activities/user_activities.html` | Mediavorschau aus `ActivityMedia` |
| `app/templates/activities/add_media.html` | **NEU** – Upload-Seite mit Drag-n-Drop für retroaktiven Upload |
| `tests/conftest.py` | `UPLOAD_FOLDER` Fixture, `tmp_path` für Test-Uploads |
| `tests/test_activities_log.py` | Upload-Tests (BytesIO), Bild + Video + Fehlerfall |
| `migrations/versions/<hash>_add_activity_media.py` | **NEU** – Alembic-Migration: `activity_media`-Tabelle + Datenmigration `screenshot_path` |

---

## Implementation Detail

### Neues Model: `ActivityMedia`

**Datei:** `app/models/activity.py` — nach Zeile 30 (nach `Activity`-Klasse)

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

Zusätzlich auf `Activity` (nach Zeile 22):
```python
media: Mapped[list["ActivityMedia"]] = relationship(
    "ActivityMedia", back_populates="activity",
    cascade="all, delete-orphan",
    order_by="ActivityMedia.created_at",
)
```

Imports ergänzen: `Integer` (SQLAlchemy), `relationship` (sqlalchemy.orm)

---

### uploads.py Änderungen

**Datei:** `app/utils/uploads.py` (aktuell 26 LOC)

```python
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
VIDEO_EXTENSIONS = {"mp4", "mov", "webm"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

def get_media_type(filename: str) -> str:
    """'image' oder 'video' anhand Extension."""
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    return "video" if ext in VIDEO_EXTENSIONS else "image"
```

`delete_upload()` bleibt für Legacy-Kompatibilität (screenshot_path). Neue Funktion:
```python
def delete_media_files(media_list) -> None:
    """Löscht alle ActivityMedia-Dateien vom Disk."""
    for media in media_list:
        delete_upload(media.file_path)
```

---

### config.py

**Zeile 16:** `MAX_CONTENT_LENGTH = 5 * 1024 * 1024` → `50 * 1024 * 1024`

---

### log_submit Route (challenge_activities.py:53-117)

**Zeile 97:** `request.files.get("screenshot")` → `request.files.getlist("media")`

Neuer Upload-Block:
```python
media_files = request.files.getlist("media")
saved_media = []
for f in media_files:
    if f and f.filename:
        path = save_upload(f)
        if path is None:
            flash("Ungültiges Dateiformat (erlaubt: JPG, PNG, WebP, MP4, MOV, WebM, max. 50 MB).")
            return redirect(url_for("challenge_activities.log_form"))
        saved_media.append((path, get_media_type(f.filename), f.filename, f.content_length or 0))
```

Nach `db.session.add(activity)` + `db.session.flush()`:
```python
for file_path, media_type, orig_name, size in saved_media:
    db.session.add(ActivityMedia(
        activity_id=activity.id,
        file_path=file_path,
        media_type=media_type,
        original_filename=orig_name,
        file_size_bytes=size,
    ))
```

---

### delete_activity Route (challenge_activities.py:357-372)

**Zeile 365-366** ersetzen:
```python
# Alt:
if activity.screenshot_path:
    delete_upload(activity.screenshot_path)

# Neu:
delete_media_files(activity.media)
if activity.screenshot_path:        # Legacy-Cleanup
    delete_upload(activity.screenshot_path)
```

---

### Neue Route: add_media (challenge_activities.py)

```python
@bp.route("/<int:activity_id>/media/add", methods=["GET", "POST"])
@login_required
def add_media(activity_id: int) -> str | Response:
    activity = db.session.get(Activity, activity_id)
    if activity is None or activity.user_id != current_user.id:
        flash("Keine Berechtigung.", "danger")
        return redirect(url_for("challenge_activities.my_week"))
    if request.method == "POST":
        media_files = request.files.getlist("media")
        for f in media_files:
            if f and f.filename:
                path = save_upload(f)
                if path is None:
                    flash("Ungültiges Dateiformat.")
                    return redirect(request.url)
                db.session.add(ActivityMedia(
                    activity_id=activity.id,
                    file_path=path,
                    media_type=get_media_type(f.filename),
                    original_filename=f.filename,
                    file_size_bytes=f.content_length or 0,
                ))
        db.session.commit()
        flash("Medien erfolgreich hinzugefügt.", "success")
        return redirect(url_for("challenge_activities.activity_detail", activity_id=activity_id))
    return render_template("activities/add_media.html", activity=activity)
```

---

### detail.html – Media-Gallery

**Zeilen 49-68 ersetzen** durch:
```html
{% if activity.media %}
<div class="card mb-4">
  <div class="card-header">Medien ({{ activity.media | length }})</div>
  <div class="card-body">
    <div class="row g-2">
      {% for m in activity.media %}
      <div class="col-6 col-md-4">
        {% if m.media_type == "video" %}
        <video src="{{ url_for('static', filename=m.file_path) }}"
               controls class="img-fluid rounded" style="max-height:200px;width:100%"></video>
        {% else %}
        <a href="{{ url_for('static', filename=m.file_path) }}" target="_blank" rel="noopener">
          <img src="{{ url_for('static', filename=m.file_path) }}"
               alt="{{ m.original_filename }}" class="img-fluid rounded" style="max-height:200px;object-fit:cover">
        </a>
        {% endif %}
      </div>
      {% endfor %}
    </div>
  </div>
</div>
{% elif activity.screenshot_path %}
{# Legacy-Fallback für alte Aktivitäten #}
<div class="card mb-4">...</div>
{% endif %}
{% if is_owner %}
<a href="{{ url_for('challenge_activities.add_media', activity_id=activity.id) }}"
   class="btn btn-outline-primary btn-sm mb-4">Medien hinzufügen</a>
{% endif %}
```

---

### log.html – Drag-n-Drop Zone

**Zeilen 23-28 ersetzen** durch Drag-n-Drop Card:
```html
<div class="mb-3">
  <label class="form-label">Fotos / Videos (optional, mehrere möglich)</label>
  <div id="drop-zone" class="border border-2 border-dashed rounded p-4 text-center text-muted"
       style="cursor:pointer;min-height:100px">
    <span id="drop-label">Dateien hier ablegen oder klicken</span><br>
    <small>JPG, PNG, WebP, MP4, MOV, WebM · max. 50 MB pro Datei</small>
    <input type="file" id="media-input" name="media" multiple
           accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
           class="d-none">
  </div>
  <div id="file-list" class="mt-2 small"></div>
</div>
<script>
(function () {
  const zone = document.getElementById('drop-zone');
  const input = document.getElementById('media-input');
  const list = document.getElementById('file-list');
  zone.addEventListener('click', () => input.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('bg-light'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('bg-light'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('bg-light');
    input.files = e.dataTransfer.files; renderList();
  });
  input.addEventListener('change', renderList);
  function renderList() {
    list.innerHTML = [...input.files].map(f =>
      `<span class="badge bg-secondary me-1">${f.name} (${(f.size/1024/1024).toFixed(1)} MB)</span>`
    ).join('');
  }
})();
</script>
```

---

### Alembic-Migration (3-Schritt für SQLite)

```python
def upgrade():
    # Schritt 1: Tabelle anlegen
    op.create_table("activity_media",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("media_type", sa.String(10), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Schritt 2: Legacy-Daten migrieren
    op.execute("""
        INSERT INTO activity_media (activity_id, file_path, media_type, original_filename, file_size_bytes, created_at)
        SELECT id, screenshot_path, 'image', 'screenshot', 0, created_at
        FROM activities
        WHERE screenshot_path IS NOT NULL
    """)
    # screenshot_path bleibt nullable – kein DROP in dieser Migration

def downgrade():
    op.drop_table("activity_media")
```

---

### Tests

**tests/conftest.py** – `TestConfig` erweitern (nach Zeile 13):
```python
import tempfile, os
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "sport_challenge_test_uploads")
```

**tests/test_activities_log.py** – neue Test-Funktionen:

- `test_log_activity_with_image`: Bild-Upload via `BytesIO`, prüft `ActivityMedia`-Eintrag in DB
- `test_log_activity_with_video`: Video-Upload (mp4), prüft `media_type == "video"`
- `test_log_activity_invalid_format`: BMP hochladen → Flash-Fehler, kein ActivityMedia-Eintrag
- `test_log_activity_no_file`: Ohne Datei → Activity gespeichert, `activity.media == []`
- `test_delete_activity_deletes_media_files`: Löschen → `delete_media_files()` aufgerufen (mock)
- `test_add_media_get`: GET `/activities/<id>/media/add` → 200, Template rendered
- `test_add_media_post`: POST mit Bild → Redirect zu detail, neuer `ActivityMedia`-Eintrag

---

## Issues

### I-01 – ActivityMedia-Model + Alembic-Migration
**Risk:** `irreversible / external / requires-approval`
**Size:** M
**Files:** `app/models/activity.py`, `migrations/versions/<hash>_add_activity_media.py`

Neues `ActivityMedia`-ORM-Model + `media`-Relation auf `Activity`. 3-Schritt-Migration:
Tabelle anlegen → bestehende `screenshot_path`-Werte migrieren → `screenshot_path` nullable lassen.

**Acceptance Criteria:**
- `flask db upgrade` läuft ohne Fehler
- `ActivityMedia`-Klasse importierbar: `from app.models.activity import ActivityMedia`
- `activity.media` liefert leere Liste für neue Activities
- `activity.media` liefert 1 Eintrag für Activities mit bestehendem `screenshot_path`
- `flask db downgrade` rollt Tabelle sauber zurück

---

### I-02 – uploads.py + config.py erweitern
**Risk:** `reversible / local / autonomous-ok`
**Size:** S
**Files:** `app/utils/uploads.py`, `config.py`

`ALLOWED_EXTENSIONS` um Video-Typen erweitern, `get_media_type()` und `delete_media_files()` hinzufügen,
`MAX_CONTENT_LENGTH` auf 50 MB erhöhen.

**Acceptance Criteria:**
- `get_media_type("clip.mp4") == "video"`
- `get_media_type("foto.jpg") == "image"`
- `allowed_file("test.webm") == True`
- `allowed_file("test.bmp") == False`
- `config.MAX_CONTENT_LENGTH == 50 * 1024 * 1024`

---

### I-03 – log_submit-Route auf Multi-File + ActivityMedia
**Risk:** `reversible / system / requires-approval`
**Size:** M
**Dependencies:** I-01, I-02
**Files:** `app/routes/challenge_activities.py`

`log_submit` auf `request.files.getlist("media")` umstellen, Loop über Uploads,
`ActivityMedia`-Einträge anlegen. `delete_activity` um `delete_media_files()` ergänzen
(plus Legacy-`screenshot_path`-Cleanup).

**Acceptance Criteria:**
- Mehrere Dateien in einem Request → mehrere `ActivityMedia`-Einträge in DB
- Ungültiges Format → Flash-Meldung, keine Aktivität gespeichert
- Activity-Delete → alle `ActivityMedia`-Dateien auf Disk gelöscht
- Bestehende `screenshot_path`-Activities: Delete löscht auch Legacy-Datei

---

### I-04 – Drag-n-Drop Log-Formular
**Risk:** `reversible / local / autonomous-ok`
**Size:** S
**Dependencies:** I-03
**Files:** `app/templates/activities/log.html`

Altes `<input type="file" name="screenshot">` ersetzen durch Drop-Zone (Bootstrap-Card + Vanilla JS).
`name="media"`, `multiple`, `accept` mit Bild + Video MIME-Types.

**Acceptance Criteria:**
- Klick auf Drop-Zone öffnet Datei-Dialog
- Drag-and-Drop akzeptiert Dateien
- Datei-Liste wird nach Auswahl angezeigt (Name + Größe)
- Formular sendet `name="media"` (plural) korrekt

---

### I-05 – Detail-Template: Media-Gallery + Upload-Button
**Risk:** `reversible / local / autonomous-ok`
**Size:** S
**Dependencies:** I-01, I-06
**Files:** `app/templates/activities/detail.html`

Screenshot-Card durch Media-Gallery ersetzen (Bild-Grid + `<video>`-Player).
Legacy-Fallback für `screenshot_path`. "Medien hinzufügen"-Button für Owner.

**Acceptance Criteria:**
- Activity mit Bildern → Grid mit `<img>`-Tags
- Activity mit Video → `<video controls>`-Element
- Activity mit 0 Medien → kein Gallery-Block
- Legacy-`screenshot_path` → Fallback-Block angezeigt
- Owner sieht "Medien hinzufügen"-Button
- Nicht-Owner sieht keinen Button

---

### I-06 – Retroaktiver Upload: Route + Template
**Risk:** `reversible / system / autonomous-ok`
**Size:** M
**Dependencies:** I-01, I-02
**Files:** `app/routes/challenge_activities.py`, `app/templates/activities/add_media.html`

Neue Route `GET/POST /activities/<id>/media/add` mit Berechtigungsprüfung (nur Owner).
Template mit Drag-n-Drop (gleiches Muster wie log.html).

**Acceptance Criteria:**
- `GET /activities/<id>/media/add` → 200 für Owner
- `GET /activities/<id>/media/add` → 302 für Nicht-Owner
- POST mit Bild → `ActivityMedia`-Eintrag + Redirect zu Detail
- POST mit ungültigem Format → Flash-Fehler, kein Eintrag

---

### I-07 – my_week.html + user_activities.html Mediavorschau
**Risk:** `reversible / local / autonomous-ok`
**Size:** S
**Dependencies:** I-01
**Files:** `app/templates/activities/my_week.html`, `app/templates/activities/user_activities.html`

Screenshot-Thumb-Block (`activity.screenshot_path`) durch Mediavorschau aus `activity.media` ersetzen
(erstes Bild als Thumbnail; bei Video: Video-Icon oder erstes Standbild).
Legacy-Fallback beibehalten.

**Acceptance Criteria:**
- Activity mit `ActivityMedia`-Bildern → erstes Bild als Thumbnail in Liste
- Activity mit nur Video → Placeholder-Icon (📹) oder `<video>`-Thumbnail
- Activity ohne Medien → kein Thumbnail
- Legacy-`screenshot_path` ohne `ActivityMedia` → Fallback-Thumbnail

---

### I-08 – Upload-Tests
**Risk:** `reversible / local / autonomous-ok`
**Size:** M
**Dependencies:** I-03, I-06
**Files:** `tests/conftest.py`, `tests/test_activities_log.py`

`UPLOAD_FOLDER` in `TestConfig`, 7 neue Test-Funktionen (s. Implementation Detail).

**Acceptance Criteria:**
- `pytest tests/test_activities_log.py -v` → alle 14 Tests grün
- Test-Upload-Verzeichnis wird nach Tests aufgeräumt (tmp_path)

---

## Wave-Struktur

```
Wave 1 (parallel):
  I-01  ActivityMedia-Model + Migration     [requires-approval]
  I-02  uploads.py + config.py erweitern   [autonomous-ok]

Wave 2 (nach Wave 1):
  I-03  log_submit Route (I-01 + I-02)     [requires-approval]
  I-06  Retroaktiver Upload Route (I-01 + I-02)
  I-07  my_week / user_activities Templates (I-01)

Wave 3 (nach Wave 2):
  I-04  Drag-n-Drop Log-Formular (I-03)
  I-05  Detail-Template Gallery (I-01 + I-06)
  I-08  Upload-Tests (I-03 + I-06)
```

---

## Boundaries

**Always:**
- `render_as_batch=True` in allen Alembic-Operationen (SQLite-Pflicht, bereits in `env.py`)
- UUID-Naming für alle Uploads (bereits `save_upload()` macht das)
- `screenshot_path` auf `Activity` bleibt nullable – kein DROP in dieser Epic
- Berechtigungsprüfung in `add_media`: nur Owner darf eigene Activity-Medien hochladen
- `MAX_CONTENT_LENGTH = 50 MB` gilt global – keine per-Route Überschreibung

**Never:**
- Kein `ffmpeg`-Einsatz in dieser Phase (Thumbnail-Generierung ist Phase II)
- Kein Dropzone.js oder andere externe JS-Bibliotheken
- Kein `multiple=True` auf `screenshot_path` – das Feld bleibt unverändert
- Kein `os.path.join` mit User-Input (Path-Traversal-Schutz: weiterhin via `static_folder`)

**Ask First:** (alle bereits entschieden)

---

## Design Decisions

| Entscheidung | Gewählt | Abgelehnt | Rationale |
|-------------|---------|-----------|-----------|
| Multi-File Storage | `ActivityMedia`-Tabelle (1:n) | Array-Feld in `Activity` | Erweiterbar, sauber querybar, CASCADE-Delete |
| Legacy-Migration | `screenshot_path` nullable belassen | DROP COLUMN | Rollback möglich ohne Datenverlust |
| Video-Serving | `<video src="...">` via Flask-Static | Streaming-Endpoint | Kein CDN nötig für lokale Deployments, einfacher |
| Drag-n-Drop | Vanilla JS | Dropzone.js | Kein npm-Dependency, Bootstrap-nativ |
| Upload-Limit | 50 MB global | Separates Video-Limit | Einfacher, für MVP ausreichend |

---

## Invalidation Risks

| Annahme | Risiko | Betroffene Issues |
|---------|--------|------------------|
| `render_as_batch=True` in env.py ist gesetzt | Gering – Commit `21c5cfd` bestätigt | I-01 |
| `activity.media` Lazy-Load in Templates | N+1-Query möglich bei vielen Activities | I-07 (ggf. `joinedload`) |
| `file.content_length` zuverlässig | Kann 0 sein (Streaming-Upload) | I-03, I-06 |
| Browser `<video>` unterstützt MP4/WebM | Hoch – alle modernen Browser | I-05 |

---

## Rollback-Strategie

**Vor Wave 1:** `git tag pre-multimedia-upload && git push origin pre-multimedia-upload`

**Wave 1 (I-01 Migration):**
- `flask db downgrade -1` rollt `activity_media`-Tabelle zurück
- `screenshot_path` bleibt intakt (nie geändert)

**Wave 2-3:**
- Git-Revert einzelner Commits, da atomar

**Komplett-Rollback:**
```bash
git checkout pre-multimedia-upload
flask db downgrade -1
```

---

## Verification

```bash
# Nach Wave 1
FLASK_APP=run.py .venv/bin/flask db upgrade
python -c "from app.models.activity import ActivityMedia; print('OK')"

# Nach Wave 2-3
.venv/bin/pytest tests/test_activities_log.py -v
.venv/bin/pytest -v  # Alle 74 Tests müssen weiter grün bleiben

# Smoke-Test Server
SECRET_KEY=<key> FLASK_DEBUG=1 .venv/bin/python run.py
# → /activities/log aufrufen, mehrere Dateien hochladen
# → Activity-Detail aufrufen, Gallery prüfen
# → /activities/<id>/media/add aufrufen
```
