# Briefing: ffh.2 – uploads.py + config.py erweitern

**Epic:** Multimedia-Upload für Aktivitäten (sport-challenge-ffh)
**Issue:** sport-challenge-ffh.2
**Wave:** 1
**Risk:** reversible / local / autonomous-ok

## Mission

Erweitere `uploads.py` um Video-Support und erhöhe `MAX_CONTENT_LENGTH` in `config.py` auf 50 MB.

## Deine Aufgabe

### 1. app/utils/uploads.py erweitern

**Datei:** `/Users/schrammn/Documents/VSCodium/sport-challenge/app/utils/uploads.py`

Lies die Datei zuerst komplett. Dann ersetze den Inhalt:

```python
import uuid
from pathlib import Path

from flask import current_app

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
VIDEO_EXTENSIONS = {"mp4", "mov", "webm"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_media_type(filename: str) -> str:
    """Gibt 'video' oder 'image' zurück, basierend auf der Dateiendung."""
    if "." not in filename:
        return "image"
    ext = filename.rsplit(".", 1)[1].lower()
    return "video" if ext in VIDEO_EXTENSIONS else "image"


def save_upload(file) -> str | None:
    if not file or not file.filename or not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    filepath = upload_dir / filename
    file.save(filepath)
    return f"uploads/{filename}"


def delete_upload(relative_path: str) -> None:
    if not relative_path:
        return
    filepath = Path(current_app.static_folder) / relative_path
    if filepath.exists():
        filepath.unlink()


def delete_media_files(media_list) -> None:
    """Löscht alle ActivityMedia-Dateien vom Disk."""
    for media in media_list:
        delete_upload(media.file_path)
```

### 2. config.py anpassen

**Datei:** `/Users/schrammn/Documents/VSCodium/sport-challenge/config.py`

Lies die Datei. Ändere nur Zeile 16:

`MAX_CONTENT_LENGTH = 5 * 1024 * 1024` → `MAX_CONTENT_LENGTH = 50 * 1024 * 1024`

### 3. Verifizieren

```bash
.venv/bin/python -c "
from app.utils.uploads import allowed_file, get_media_type, ALLOWED_EXTENSIONS
print('jpg:', allowed_file('test.jpg'))      # True
print('mp4:', allowed_file('test.mp4'))      # True
print('bmp:', allowed_file('test.bmp'))      # False
print('video type mp4:', get_media_type('clip.mp4'))   # video
print('image type jpg:', get_media_type('foto.jpg'))   # image
print('All OK')
"
```

## File Ownership

**Nur diese Dateien ändern:**
- `app/utils/uploads.py`
- `config.py`

**Nicht anfassen:**
- Alle anderen Dateien

## Acceptance Criteria

- [ ] `allowed_file("test.webm") == True`
- [ ] `allowed_file("test.mp4") == True`
- [ ] `allowed_file("test.bmp") == False`
- [ ] `get_media_type("clip.mp4") == "video"`
- [ ] `get_media_type("foto.jpg") == "image"`
- [ ] `delete_media_files([])` läuft ohne Fehler
- [ ] `config.MAX_CONTENT_LENGTH == 50 * 1024 * 1024`

## Boundaries (IMMER einhalten)

- `delete_upload()` bleibt für Legacy-Kompatibilität (screenshot_path) erhalten
- Kein Committen – nur Code-Änderungen schreiben

## Output-Format

Antworte am Ende mit:

RESULT_START
STATUS: COMPLETE|BLOCKED|DESIGN_DECISION_REQUIRED
FILES_MODIFIED: app/utils/uploads.py, config.py
SUMMARY: <1-2 Sätze was gemacht wurde>
BLOCKERS: <leer oder Beschreibung>
RESULT_END
