import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable is required and must not be empty")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///sport-challenge.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
    STRAVA_CLIENT_ID: str = os.environ.get("STRAVA_CLIENT_ID", "")
    STRAVA_CLIENT_SECRET: str = os.environ.get("STRAVA_CLIENT_SECRET", "")
    _default_upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static", "uploads")
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", _default_upload_folder)
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
