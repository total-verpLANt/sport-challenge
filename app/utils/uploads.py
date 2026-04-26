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
