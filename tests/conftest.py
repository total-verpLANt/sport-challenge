import io
import os
import shutil
import subprocess
import tempfile

import pytest
from PIL import Image

from app import create_app
from app.extensions import db as _db


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret-key-not-for-production"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "sport_challenge_test_uploads")


@pytest.fixture(scope="session")
def app():
    app = create_app(TestConfig)
    return app


@pytest.fixture()
def db(app):
    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture()
def client(app, db):
    return app.test_client()


# ---------------------------------------------------------------------------
# Echte Mediendaten für Upload-Tests (Issue 43k: Inhalt wird serverseitig
# validiert, gefälschte Dummy-Bytes werden abgelehnt).
# ---------------------------------------------------------------------------

def _image_bytes(fmt: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), "red").save(buf, fmt)
    return buf.getvalue()


@pytest.fixture(scope="session")
def sample_png_bytes() -> bytes:
    return _image_bytes("PNG")


@pytest.fixture(scope="session")
def sample_jpeg_bytes() -> bytes:
    return _image_bytes("JPEG")


@pytest.fixture(scope="session")
def sample_mp4_bytes(tmp_path_factory) -> bytes:
    """Erzeugt einmalig ein gültiges Mini-MP4 via ffmpeg. Ohne ffmpeg → Skip."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg nicht verfügbar")
    out = tmp_path_factory.mktemp("media") / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=32x32:d=1",
         "-pix_fmt", "yuv420p", str(out)],
        capture_output=True, check=True,
    )
    return out.read_bytes()
