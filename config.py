import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-in-prod")
    GARMIN_EMAIL = os.environ.get("GARMIN_EMAIL")
    GARMIN_PASSWORD = os.environ.get("GARMIN_PASSWORD")
    GARMIN_TOKEN_DIR = os.environ.get(
        "GARMINTOKENS", os.path.expanduser("~/.garminconnect")
    )
