# Briefing: 1.5 Upload-Utility + Config

## Mission
Epic: Challenge-System — Implementierung des vollständigen Challenge-Systems.

## Your Task
1. Erstelle `app/utils/uploads.py` mit Upload-Handling (UUID-Benennung, Typ-Validierung, Größenlimit)
2. Erweitere `config.py` um UPLOAD_FOLDER und MAX_CONTENT_LENGTH

## Cross-Cutting Constraints
- File-Upload: UUID-Dateinamen, Typ-Validierung server-seitig, 5 MB Limit
- Niemals Dateinamen vom Client übernehmen (Path-Traversal-Schutz)
- Screenshots nur in app/static/uploads/ speichern

## Current config.py content:
```python
import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable is required and must not be empty")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///sport-challenge.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
    STRAVA_CLIENT_ID: str = os.environ.get("STRAVA_CLIENT_ID", "")
    STRAVA_CLIENT_SECRET: str = os.environ.get("STRAVA_CLIENT_SECRET", "")
```

## Deliverable

### File 1: `app/utils/uploads.py` (NEW)
```python
import uuid
from pathlib import Path
from flask import current_app

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

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
```

### File 2: `config.py` (MODIFY — add 2 lines)
Add these two lines at the end of the Config class:
```python
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
```

## File Ownership
- Create: `app/utils/uploads.py` (NEW)
- Modify: `config.py` (add 2 lines only)
- Do NOT modify any other files

## Verification
```bash
SECRET_KEY=test .venv/bin/python -c "from app.utils.uploads import save_upload, delete_upload, allowed_file; print(allowed_file('test.jpg'), allowed_file('test.exe')); print('OK')"
```
Expected: `True False` then `OK`

## Output Format
```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/utils/uploads.py, config.py
SUMMARY: Created upload utility with UUID naming, type validation, 5MB limit; updated config
RESULT_END
```
