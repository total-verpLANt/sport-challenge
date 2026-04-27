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
