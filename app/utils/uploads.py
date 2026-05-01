import json
import subprocess
import uuid
from datetime import datetime, timezone
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
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    # .name extrahiert nur den Dateinamen – verhindert Path-Traversal via "uploads/../.."
    filename = Path(relative_path).name
    filepath = (upload_dir / filename).resolve()
    if not filepath.is_relative_to(upload_dir):
        current_app.logger.warning("delete_upload: path traversal blocked: %s", relative_path)
        return
    if filepath.exists():
        filepath.unlink()


def extract_video_recorded_at(relative_path: str) -> datetime | None:
    """Liest creation_time aus dem Video-Container via ffprobe. Gibt None zurück wenn nicht verfügbar."""
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    filename = Path(relative_path).name
    filepath = upload_dir / filename
    if not filepath.exists():
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_entries", "format_tags=creation_time",
                str(filepath),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = json.loads(result.stdout)
        creation_time_str = data.get("format", {}).get("tags", {}).get("creation_time")
        if not creation_time_str:
            return None
        # Format: "2026-04-27T14:35:00.000000Z"
        return datetime.fromisoformat(creation_time_str.replace("Z", "+00:00"))
    except Exception:
        return None


def delete_media_files(media_list) -> None:
    """Löscht alle ActivityMedia-Dateien vom Disk."""
    for media in media_list:
        delete_upload(media.file_path)
