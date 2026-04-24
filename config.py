import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    GARMIN_TOKEN_DIR = os.environ.get(
        "GARMIN_TOKEN_DIR", os.path.expanduser("~/.garminconnect")
    )
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///sport-challenge.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
