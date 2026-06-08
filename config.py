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
    MAILGUN_API_KEY: str = os.environ.get("MAILGUN_API_KEY", "")
    MAILGUN_DOMAIN: str = os.environ.get("MAILGUN_DOMAIN", "")
    MAILGUN_SENDER: str = os.environ.get("MAILGUN_SENDER", "")
    # EU-Region: https://api.eu.mailgun.net/v3
    MAILGUN_BASE_URL: str = os.environ.get("MAILGUN_BASE_URL", "https://api.mailgun.net/v3")

    # Host-Header-Härtung (siehe haf): externe Links nicht aus dem Request-Host ableiten.
    # PUBLIC_BASE_URL: kanonische Basis für Mail-/OAuth-URLs, z. B. https://sport.example.com
    PUBLIC_BASE_URL: str | None = os.environ.get("PUBLIC_BASE_URL") or None
    # TRUSTED_HOSTS: komma-getrennte Allowlist; Flask weist fremde Host-Header mit 400 ab.
    TRUSTED_HOSTS: list[str] | None = [
        h.strip() for h in os.environ.get("TRUSTED_HOSTS", "").split(",") if h.strip()
    ] or None
    # ProxyFix darf X-Forwarded-Host nur vertrauen, wenn die Proxy-Kette ihn garantiert setzt.
    PROXY_X_HOST: int = int(os.environ.get("PROXY_X_HOST", "0"))
