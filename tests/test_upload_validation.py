"""Upload-Inhaltsvalidierung (Issue 43k)

Abdeckung:
  1. Extension-Spoofing Bild: HTML/Text als .jpg → abgelehnt, kein Orphan
  2. Extension-Spoofing Video: Text als .mp4 → abgelehnt, kein Orphan
  3. Bild-Inhalt als .mp4 (ffprobe sieht Einzelbild als video) → via Container abgelehnt
  4. Happy Path: gültiges PNG/JPEG/WEBP → akzeptiert
  5. Happy Path: gültiges MP4 → akzeptiert
  6. Cleanup: abgelehnte Uploads hinterlassen keine Dateien im Upload-Ordner

Hinweis: Video-Tests brauchen ffmpeg/ffprobe. Fehlt das Binary, werden sie geskippt.
"""

import io
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.utils.uploads import save_upload


# ---------------------------------------------------------------------------
# Fixtures / Helfer
# ---------------------------------------------------------------------------

@pytest.fixture()
def upload_dir(app, tmp_path):
    """App-Context mit isoliertem Upload-Ordner pro Test (kein Cross-Test-Leak)."""
    with app.app_context():
        old = app.config.get("UPLOAD_FOLDER")
        app.config["UPLOAD_FOLDER"] = str(tmp_path)
        yield tmp_path
        app.config["UPLOAD_FOLDER"] = old


def _fs(data: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(data), filename=filename)


def _image_bytes(fmt: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), "red").save(buf, fmt)
    return buf.getvalue()


def _files_in(directory: Path) -> list[Path]:
    return [p for p in Path(directory).iterdir() if p.is_file()]


@pytest.fixture(scope="session")
def sample_mp4_bytes(tmp_path_factory) -> bytes:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg nicht verfügbar")
    out = tmp_path_factory.mktemp("vid") / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=32x32:d=1",
         "-pix_fmt", "yuv420p", str(out)],
        capture_output=True, check=True,
    )
    return out.read_bytes()


# ---------------------------------------------------------------------------
# Spoofing wird abgelehnt
# ---------------------------------------------------------------------------

def test_html_as_jpg_rejected(upload_dir):
    path, reason = save_upload(_fs(b"<html><script>alert(1)</script></html>", "evil.jpg"))
    assert path is None
    assert "beschädigt" in reason  # sprechender Grund statt Pauschaltext
    assert _files_in(upload_dir) == []  # kein Orphan


def test_text_as_png_rejected(upload_dir):
    path, reason = save_upload(_fs(b"definitely not a png", "fake.png"))
    assert path is None
    assert "Bild" in reason
    assert _files_in(upload_dir) == []


def test_text_as_mp4_rejected(upload_dir):
    if shutil.which("ffprobe") is None:
        pytest.skip("ffprobe nicht verfügbar")
    path, reason = save_upload(_fs(b"this is plain text, not a video", "fake.mp4"))
    assert path is None
    assert "Video" in reason
    # Video wird erst gespeichert, dann via ffprobe geprüft → Datei muss wieder weg sein
    assert _files_in(upload_dir) == []


def test_image_content_as_mp4_rejected(upload_dir):
    """Ein echtes PNG mit .mp4-Endung: ffprobe meldet zwar einen video-Stream,
    aber der Container (png_pipe) ist kein erlaubter Video-Container → abgelehnt."""
    if shutil.which("ffprobe") is None:
        pytest.skip("ffprobe nicht verfügbar")
    path, reason = save_upload(_fs(_image_bytes("PNG"), "image.mp4"))
    assert path is None
    assert reason
    assert _files_in(upload_dir) == []


# ---------------------------------------------------------------------------
# Gültige Medien werden weiterhin akzeptiert
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fmt,ext", [("PNG", "png"), ("JPEG", "jpg"), ("WEBP", "webp")])
def test_valid_image_accepted(upload_dir, fmt, ext):
    path, reason = save_upload(_fs(_image_bytes(fmt), f"good.{ext}"))
    assert reason is None
    assert path.startswith("uploads/")
    assert len(_files_in(upload_dir)) == 1


def test_valid_mp4_accepted(upload_dir, sample_mp4_bytes):
    path, reason = save_upload(_fs(sample_mp4_bytes, "clip.mp4"))
    assert reason is None
    assert path.startswith("uploads/")
    assert len(_files_in(upload_dir)) == 1


# ---------------------------------------------------------------------------
# Bestehendes Verhalten: unerlaubte Endung wird vor jeder Inhaltsprüfung abgewiesen
# ---------------------------------------------------------------------------

def test_disallowed_extension_rejected(upload_dir):
    path, reason = save_upload(_fs(_image_bytes("PNG"), "sneaky.svg"))
    assert path is None
    # Grund nennt die konkrete Endung → Nutzer weiß, warum
    assert ".svg" in reason
    assert _files_in(upload_dir) == []
