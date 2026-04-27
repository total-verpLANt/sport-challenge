# Briefing: ffh.3 – log_submit Route auf Multi-File + ActivityMedia

**Epic:** Multimedia-Upload für Aktivitäten (sport-challenge-ffh)
**Issue:** sport-challenge-ffh.3
**Wave:** 2

## Kontext

Wave 1 ist abgeschlossen:
- `ActivityMedia`-Model existiert in `app/models/activity.py`
- `get_media_type()` und `delete_media_files()` existieren in `app/utils/uploads.py`
- `ALLOWED_EXTENSIONS` enthält jetzt auch Video-Typen

## Deine Aufgabe

Datei: `app/routes/challenge_activities.py`

Lies die Datei ZUERST vollständig. Dann:

### Änderung 1: Imports erweitern

Suche den Import-Block. Füge `ActivityMedia` zum Import von `app.models.activity` hinzu:
```python
from app.models.activity import Activity, ActivityMedia
```
Und `delete_media_files` + `get_media_type` zum Import von `app.utils.uploads`:
```python
from app.utils.uploads import delete_upload, delete_media_files, get_media_type, save_upload
```

### Änderung 2: log_submit (Zeilen ~95-115) – Upload auf Multi-File umstellen

Ersetze den Screenshot-Upload-Block:
```python
# ALT (ca. Zeile 96-111):
screenshot_path = None
screenshot_file = request.files.get("screenshot")
if screenshot_file and screenshot_file.filename:
    screenshot_path = save_upload(screenshot_file)
    if screenshot_path is None:
        flash("Ungültiges Dateiformat für Screenshot (erlaubt: JPG, PNG, WebP, max. 5 MB).")
        return redirect(url_for("challenge_activities.log_form"))
...
activity = Activity(
    ...
    screenshot_path=screenshot_path,
)
```

Durch folgenden Block ersetzen:
```python
# NEU:
media_files = request.files.getlist("media")
saved_media = []
for f in media_files:
    if f and f.filename:
        path = save_upload(f)
        if path is None:
            flash("Ungültiges Dateiformat (erlaubt: JPG, PNG, WebP, MP4, MOV, WebM, max. 50 MB).")
            return redirect(url_for("challenge_activities.log_form"))
        saved_media.append((path, get_media_type(f.filename), f.filename))
```

Dann beim Anlegen der Activity `screenshot_path=screenshot_path` entfernen. Nach `db.session.add(activity)` + `db.session.flush()` die ActivityMedia-Einträge anlegen:
```python
db.session.add(activity)
db.session.flush()  # activity.id wird damit gesetzt
for file_path, media_type, orig_name in saved_media:
    db.session.add(ActivityMedia(
        activity_id=activity.id,
        file_path=file_path,
        media_type=media_type,
        original_filename=orig_name,
        file_size_bytes=0,
    ))
db.session.commit()
```

**WICHTIG:** Prüfe ob `db.session.flush()` bereits vorhanden ist oder ob erst `commit()` kommt. Passe entsprechend an.

### Änderung 3: delete_activity – ActivityMedia + Legacy löschen

Suche `delete_activity` (Zeilen ~357-372). Ersetze den Screenshot-Lösch-Block:
```python
# ALT:
if activity.screenshot_path:
    delete_upload(activity.screenshot_path)

# NEU:
delete_media_files(activity.media)
if activity.screenshot_path:        # Legacy-Cleanup
    delete_upload(activity.screenshot_path)
```

## File Ownership

**Nur diese Datei ändern:**
- `app/routes/challenge_activities.py`

## Acceptance Criteria

- [ ] `request.files.getlist("media")` wird verwendet (nicht `.get()`)
- [ ] ActivityMedia-Einträge werden nach `flush()` angelegt
- [ ] `screenshot_path=` wird nicht mehr in Activity-Konstruktor übergeben
- [ ] `delete_activity` ruft `delete_media_files(activity.media)` auf
- [ ] Legacy-`screenshot_path`-Cleanup bleibt erhalten

## Boundaries

- Kein `screenshot_path` aus Activity-Model entfernen
- Kein Committen
- `db.session.flush()` vor ActivityMedia-Einträgen verwenden

## Output-Format

RESULT_START
STATUS: COMPLETE|BLOCKED|DESIGN_DECISION_REQUIRED
FILES_MODIFIED: app/routes/challenge_activities.py
SUMMARY: <1-2 Sätze>
BLOCKERS: <leer oder Beschreibung>
RESULT_END
