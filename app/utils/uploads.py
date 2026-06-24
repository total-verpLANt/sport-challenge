import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app
from PIL import Image

# HEIC/HEIF (iPhone-Standardformat) via pillow-heif. Defensiver Import: fehlt die
# Lib (oder libheif) im laufenden Image, bleibt die App lauffähig und HEIC wird
# einfach nicht erlaubt – statt die ganze App beim Start zu brechen.
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    _HEIF_SUPPORTED = True
except Exception:  # pragma: no cover - Fallback bei fehlender pillow-heif/libheif
    _HEIF_SUPPORTED = False

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
VIDEO_EXTENSIONS = {"mp4", "mov", "webm"}

# Pillow-Format-Namen, die zu den erlaubten Bild-Endungen passen (Inhalts-Allowlist).
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}

# HEIC/HEIF nur freigeben, wenn der Decoder wirklich da ist. Pillow meldet HEIC
# unter dem Format-Namen "HEIF". Ist die Lib nicht verfügbar, erhält ein
# heic-Upload die ehrliche "nicht unterstützt"-Meldung statt "beschädigt".
if _HEIF_SUPPORTED:
    IMAGE_EXTENSIONS |= {"heic", "heif"}
    ALLOWED_IMAGE_FORMATS |= {"HEIF"}

ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
# ffprobe-Container-Tokens echter Video-Container. Wichtig: ffprobe meldet auch für
# Einzelbilder (z. B. PNG → "png_pipe") einen codec_type=video-Stream. Erst der
# Container-Abgleich verhindert, dass ein Bild mit .mp4-Endung als Video durchrutscht.
ALLOWED_VIDEO_CONTAINERS = {"mov", "mp4", "matroska", "webm"}
# Schutz gegen Decompression-Bombs: winzige Datei, riesige Pixelfläche. Pillow wirft
# darüber eine DecompressionBombError, die wir als ungültig behandeln.
Image.MAX_IMAGE_PIXELS = 50_000_000


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _is_valid_image(stream) -> bool:
    """Prüft via Pillow, ob der Stream ein dekodierbares Bild eines erlaubten Formats ist.

    Spult den Stream danach wieder auf 0 zurück, damit der anschließende file.save()
    die vollständige Datei schreibt. Verlässt sich NICHT auf die Dateiendung oder den
    vom Client gelieferten Content-Type.
    """
    try:
        img = Image.open(stream)
        fmt = img.format
        img.verify()  # Integritätsprüfung (Header/CRC), ohne vollständiges Rendern
    except Exception:
        return False
    finally:
        try:
            stream.seek(0)
        except (OSError, ValueError):
            pass
    return fmt in ALLOWED_IMAGE_FORMATS


def _is_valid_video(filepath: Path) -> bool:
    """Prüft via ffprobe, ob die Datei ein echtes Video eines erlaubten Containers ist.

    Zwei Bedingungen müssen erfüllt sein: (1) der Container gehört zu einem erlaubten
    Video-Format und (2) es existiert ein Video-Stream. (1) ist nötig, weil ffprobe
    Einzelbilder ebenfalls als codec_type=video meldet.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=format_name:stream=codec_type",
                "-of", "json",
                str(filepath),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = json.loads(result.stdout or "{}")
        format_name = data.get("format", {}).get("format_name", "")
        containers = {token.strip() for token in format_name.split(",") if token.strip()}
        if not (containers & ALLOWED_VIDEO_CONTAINERS):
            return False
        return any(s.get("codec_type") == "video" for s in data.get("streams", []))
    except Exception:
        return False


def get_media_type(filename: str) -> str:
    """Gibt 'video' oder 'image' zurück, basierend auf der Dateiendung."""
    if "." not in filename:
        return "image"
    ext = filename.rsplit(".", 1)[1].lower()
    return "video" if ext in VIDEO_EXTENSIONS else "image"


def save_upload(file) -> tuple[str | None, str | None]:
    """Speichert einen Upload. Rückgabe: ``(relativer_pfad, fehlergrund)``.

    Bei Erfolg ``(pfad, None)``, bei Ablehnung ``(None, grund)``. Der Grund ist
    kurz und nutzerfreundlich formuliert und kann direkt geflasht werden, damit
    der Nutzer erfährt, *warum* der Upload scheiterte (falsche Endung vs.
    beschädigter/unlesbarer Inhalt) – ohne interne Details preiszugeben.
    """
    if not file or not file.filename:
        return None, "Keine Datei ausgewählt."
    if not allowed_file(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        detail = f".{ext}" if ext else "ohne Endung"
        return None, f"Dateiformat {detail} wird nicht unterstützt."
    media_type = get_media_type(file.filename)

    # Bilder VOR dem Speichern aus dem Stream validieren → eine abgelehnte Datei
    # landet gar nicht erst auf der Disk (kein Orphan möglich).
    if media_type == "image" and not _is_valid_image(file.stream):
        current_app.logger.warning("save_upload: Bild-Inhalt ungültig, abgelehnt: %s", file.filename)
        return None, "Bild beschädigt oder unlesbar."

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    filepath = upload_dir / filename
    file.save(filepath)

    # Videos braucht ffprobe als Datei auf der Disk. Bei ungültigem Inhalt die
    # bereits gespeicherte Datei sofort wieder entfernen (kein Orphan).
    if media_type == "video" and not _is_valid_video(filepath):
        filepath.unlink(missing_ok=True)
        current_app.logger.warning("save_upload: Video-Inhalt ungültig, abgelehnt: %s", file.filename)
        return None, "Video beschädigt oder unlesbar."

    return f"uploads/{filename}", None


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
