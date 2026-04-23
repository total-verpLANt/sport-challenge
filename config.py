import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-in-prod")
    GARMIN_TOKEN_DIR = os.environ.get(
        "GARMINTOKENS", os.path.expanduser("~/.garminconnect")
    )
