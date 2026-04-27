# Research: Multimedia-Upload für Aktivitäten

**Date:** 2026-04-27
**Scope:** Upload-System, Activity-Model, Aktivitäts-Routen & Templates, Tests

---

## Executive Summary

- Das aktuelle Upload-System ist **Single-File-only**: ein `screenshot_path`-Feld (String(500)) pro Activity-DB-Zeile, kein Multi-File-Support im Model oder Code.
- `uploads.py` ist minimal und sauber: UUID-Naming, 4 erlaubte Bildtypen (jpg, jpeg, png, webp), 5 MB via `MAX_CONTENT_LENGTH`. Kein Video-Support.
- Die Activity-Detail-Route und das Template existieren bereits (I-01); Screenshot wird dort schon als vollbild-Img gerendert.
- Für Multi-File + Video muss eine neue **`ActivityMedia`-Tabelle** her (1:n statt 1:1) – das ist die größte DB-Änderung (Migration + Alembic).
- Es gibt **null Upload-Tests** – das ist ein Risiko, das mit dem Feature mitbehoben werden sollte.

---

## Key Files

| File | Purpose |
|------|---------|
| `app/utils/uploads.py` | `allowed_file()` + `save_upload()` + `delete_upload()` |
| `app/models/activity.py` | Activity-Model mit `screenshot_path: String(500)` |
| `app/routes/challenge_activities.py` | 8 Routen inkl. `log_submit`, `activity_detail`, `delete_activity` |
| `app/templates/activities/detail.html` | Detail-Ansicht (70 Zeilen), zeigt Screenshot als Card |
| `app/templates/activities/log.html` | Log-Formular mit einfachem `<input type="file">` |
| `app/templates/activities/my_week.html` | Listet Aktivitäten der Woche mit Mini-Screenshot-Thumb |
| `app/templates/activities/user_activities.html` | Fremde Aktivitäten (Challenge-Teilnehmer-Sicht) |
| `config.py` | `UPLOAD_FOLDER`, `MAX_CONTENT_LENGTH = 5 MB` |
| `tests/conftest.py` | Fixtures – kein UPLOAD_FOLDER-Setup |
| `tests/test_activities_log.py` | 7 Tests, 0 Upload-Tests |

---

## Technology Stack

| Library/Framework | Version | Role |
|-------------------|---------|----|
| Flask | 3.x | Request-Handling, `url_for('static', ...)` |
| Werkzeug | 3.x | `FileStorage.save()`, Datei-Streaming |
| SQLAlchemy | 2.x | ORM, Mapped-Columns, Alembic-Migrations |
| Bootstrap | 5.3.3 | Frontend-Components (Cards, Grid) |
| Jinja2 | 3.x | Template-Rendering |

---

## Findings

### F-01: Activity-Model – Single-File-Feld

`app/models/activity.py` hat:
```python
screenshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
```
Dieses Feld speichert `"uploads/{uuid4hex}.{ext}"`. Es ist 1:1 mit der Activity. Für Multi-File muss dieses Feld entweder:
- (a) **deprecated** und durch `ActivityMedia`-Relation ersetzt werden, oder
- (b) als Legacy-Feld behalten und eine neue Tabelle daneben gestellt werden (Migration-Aufwand niedriger, aber technische Schulden).

Empfehlung: **Option (a)** – saubere Ablösung, `screenshot_path` via Migration auf `NULL` setzen und langfristig entfernen.

### F-02: uploads.py – Minimaler, aber sauberer Code

`app/utils/uploads.py`:
- `ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}` – kein Video
- `save_upload(file) -> str | None` – nimmt einzelnen `FileStorage`, gibt relativ-Pfad zurück
- `delete_upload(relative_path)` – prüft `.exists()`, löscht sicher

Für Multi-File und Video muss:
1. `ALLOWED_EXTENSIONS` um `{"mp4", "mov", "webm", "avi"}` erweitert werden
2. Eine neue `save_uploads(files: list) -> list[str]` oder Loop um `save_upload` entstehen
3. Separates Größen-Limit für Videos sinnvoll (50 MB? konfigurierbar?)

### F-03: log_submit-Route – Single-File-Upload

`app/routes/challenge_activities.py:97-102`:
```python
screenshot_file = request.files.get("screenshot")  # singular!
if screenshot_file and screenshot_file.filename:
    screenshot_path = save_upload(screenshot_file)
```
`request.files.get()` holt nur **eine Datei**. Für Multi-File muss `request.files.getlist("media")` verwendet werden.

### F-04: Detail-Template – Screenshot als Card (ausbaubar)

`app/templates/activities/detail.html:49-68`: Screenshot-Card existiert bereits – gibt eine saubere Stelle, an der eine **Media-Gallery** (mehrere Bilder + Video-Player) eingefügt werden kann. Die Card-Struktur muss nur erweitert werden.

### F-05: Keine Upload-Tests

`tests/test_activities_log.py` hat 229 Zeilen, 7 Tests – kein einziger testet Upload-Pfade. `conftest.py` hat keinen `UPLOAD_FOLDER`-Config für Tests. Uploads im Test simulieren via `BytesIO` + `content_type='multipart/form-data'` ist möglich, fehlt nur.

### F-06: Detail-Route existiert (I-01)

`GET /activities/<int:activity_id>` → `activity_detail()` mit Berechtigungsprüfung (Eigentümer oder Challenge-Teilnehmer). Ideal als Ziel für retroaktive Upload-Funktion. Ein "Medien hinzufügen"-Button kann direkt dort platziert werden.

### F-07: Drag-n-Drop – kein nativer Browser-Support nötig

Drag-n-Drop File-Upload kann **ohne externe Library** via HTML5 `dragover` / `drop` Events + `<input type="file" multiple>` implementiert werden. Bootstrap 5 hat dafür kein fertiges Komponente, aber die Umsetzung ist ~50 Zeilen vanilla JS. Alternativ: [Dropzone.js](https://www.dropzone.dev/) (MIT, no dependencies).

---

## Notwendige DB-Änderung: ActivityMedia-Tabelle

```
ActivityMedia
├── id (PK)
├── activity_id (FK activities.id, ON DELETE CASCADE)
├── file_path (String 500)          # "uploads/{uuid}.{ext}"
├── media_type (String 10)          # "image" | "video"
├── original_filename (String 255)  # für Download-Label
├── file_size_bytes (Integer)       # für Info-Anzeige
└── created_at (DateTime)
```

Migration: 3-Schritt (wie bei UUID-Feature):
1. Neue Tabelle erstellen
2. Bestehende `screenshot_path`-Werte migrieren (INSERT INTO activity_media)
3. `screenshot_path` auf Activity nullable lassen (nicht direkt entfernen, um Rollback zu ermöglichen)

---

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| uploads.py Implementierung | 4 | Vollständig gelesen, alle Funktionen verstanden |
| Activity-Model | 4 | Alle Felder bekannt |
| challenge_activities.py Routen | 3 | Key-Routen gelesen, Upload-Flow klar |
| Detail-Template | 4 | Vollständig gelesen |
| Log-Template | 3 | Input-Struktur bekannt |
| Test-Coverage | 4 | Alle Tests gelesen, Lücken bekannt |
| DB-Migrationsstrategie | 2 | Bekannt aus Praxis (UUID-Feature), aber konkrete Steps noch nicht geplant |
| Drag-n-Drop JS | 1 | Ansatz bekannt, konkrete Implementierung noch nicht geplant |

---

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Video-Größen-Limit: 5 MB reicht nicht | must-fill | Kapitän entscheiden lassen: 50 MB? Config-Variable? |
| Video-Streaming vs. Full-Download | must-fill | `<video>`-Tag genügt für lokale Files; kein CDN nötig |
| MIME-Type-Validierung zusätzlich zu Extension | nice-to-have | `python-magic` oder `imghdr` für Serverside-Checks |
| Thumbnail-Generierung für Videos | nice-to-have | `ffmpeg` via subprocess – Complexity hoch, kein MVP |
| Upload-Progress im Browser | nice-to-have | XHR/Fetch statt form-submit nötig |
| Disk-Space-Management | nice-to-have | Kein Cleanup-Job für verwaiste Dateien |

---

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| `screenshot_path` wird bei Activity-Delete korrekt gelöscht | Yes | `challenge_activities.py:366` |
| Flask `MAX_CONTENT_LENGTH` gilt global für alle Requests | Yes | Flask-Docs (5 MB aktuell) |
| `static/uploads/` ist Serve-Pfad für alle Medien | Yes | `url_for('static', filename=activity.screenshot_path)` |
| Alembic render_as_batch=True ist gesetzt | Yes | Commit `21c5cfd` – bereits nachgezogen |
| Drag-n-Drop ohne externe Library machbar | No | Nur Allgemeinwissen, kein Code evaluiert |
| Videos können direkt mit `<video>`-Tag served werden | No | Abhängig von Browser-Codec-Support |

---

## Recommendations

### Scope für MVP (Phase I)

1. **`ActivityMedia`-Tabelle** (DB-Migration) – 1:n zur Activity
2. **`uploads.py` erweitern** – Video-Extensions, `save_uploads()` für Batch
3. **Log-Formular** – Drag-n-Drop mit `multiple`, ersetzt altes `<input type="file">`
4. **`log_submit`-Route** – `request.files.getlist()`, Loop über `save_upload()`
5. **Detail-Template** – Media-Gallery (Bild-Grid + `<video>`-Player)
6. **Nachträglicher Upload** – neue Route `POST /activities/<id>/upload` + Upload-Seite mit Drag-n-Drop
7. **Retroaktiver Upload-Button** in Detail-Template
8. **Tests** – BytesIO-basiert, Fixtures für UPLOAD_FOLDER

### Scope für Phase II (later)

- Thumbnail-Generierung für Videos (ffmpeg)
- Upload-Progress-Bar (XHR/Fetch)
- MIME-Type-Serverside-Check (python-magic)
- Disk-Cleanup-Job für verwaiste Dateien

### MAX_CONTENT_LENGTH

**Entscheidung Kapitän 2026-04-27:** `MAX_CONTENT_LENGTH` wird auf **50 MB** erhöht (bisher 5 MB). Gilt global. Kurze Sport-Clips (1–2 Min.) passen damit problemlos rein.

### Drag-n-Drop UI

**Entscheidung Kapitän 2026-04-27:** **Vanilla JS** – kein Dropzone.js, keine externe Library. Bootstrap-Card als Drop-Zone, eigenes JS (~50 Zeilen). Kein npm-Dependency.

### Security-Hinweise

- Extension-Whitelist ist gut, aber MIME-Type-Check fehlt (Extension spoof möglich)
- UUID-Naming verhindert Path-Traversal
- `delete_upload()` prüft `.exists()` – kein Pfad-Traversal-Risk (baut via `static_folder`)
- Video-Files sollten ebenfalls UUID-genamtet sein (bereits durch `save_upload()` gegeben)
