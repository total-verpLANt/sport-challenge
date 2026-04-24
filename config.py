import os


class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]
    GARMIN_TOKEN_DIR = os.environ.get(
        "GARMINTOKENS", os.path.expanduser("~/.garminconnect")
    )
