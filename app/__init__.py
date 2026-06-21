import gzip
import logging
import shutil
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, g, redirect, request, url_for
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config

_LOG_FORMAT = "%(asctime)s %(levelname)-5s %(name)s %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _gzip_rotator(source, dest):
    """Rotiert eine volle Logdatei: komprimiert <source> nach <dest> (gzip)
    und entfernt das unkomprimierte Original. So bleiben rotierte Logs als
    Archiv erhalten, statt unkomprimiert verworfen zu werden."""
    with open(source, "rb") as f_in, gzip.open(dest, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    Path(source).unlink()


def _gzip_namer(name):
    """Hängt .gz an den Namen der rotierten Datei (z.B. access.log.1.gz)."""
    return name + ".gz"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # x_host nur vertrauen, wenn die Proxy-Kette X-Forwarded-Host garantiert setzt (siehe haf).
    # TRUSTED_HOSTS aus der Config wird von Flask 3.1 automatisch zur Host-Validierung genutzt.
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=app.config.get("PROXY_X_HOST", 0)
    )

    if not app.debug:
        logging.basicConfig(
            level=logging.INFO,
            format=_LOG_FORMAT,
            datefmt=_LOG_DATE_FORMAT,
        )

    log_dir = Path(app.root_path).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    # WARNUNG: RotatingFileHandler ist nur fuer EINEN schreibenden Prozess sicher.
    # Bei GUNICORN_WORKERS > 1 muss auf concurrent-log-handler (Datei-Locking)
    # umgestellt werden, sonst drohen korrupte/verlorene Logzeilen bei Rotation.
    file_handler = RotatingFileHandler(
        log_dir / "access.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    # Rotierte Logs gzip-archivieren statt unkomprimiert zu verwerfen.
    file_handler.rotator = _gzip_rotator
    file_handler.namer = _gzip_namer
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT))
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)

    from app.extensions import csrf, db, limiter, login_manager, migrate, talisman
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    csp = {
        "default-src": "'self'",
        "script-src": "'self' cdn.jsdelivr.net",
        "style-src": "'self' 'unsafe-inline' cdn.jsdelivr.net",
        "img-src": "'self' data:",
        "media-src": "'self'",
    }
    talisman.init_app(
        app,
        content_security_policy=csp,
        content_security_policy_nonce_in=["script-src"],
        force_https=False,
    )

    @app.before_request
    def _log_request_start():
        g.request_start = time.monotonic()

    @app.after_request
    def _log_request(response):
        duration_ms = int((time.monotonic() - g.get("request_start", time.monotonic())) * 1000)
        user_id = current_user.id if current_user.is_authenticated else "anon"
        app.logger.info(
            "%s %s %s %d %dms user=%s",
            request.remote_addr,
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            user_id,
        )
        return response

    from app.models.activity import Activity  # noqa: F401 – Alembic autogenerate
    from app.models.bonus import BonusChallenge, BonusChallengeEntry  # noqa: F401
    from app.models.challenge import Challenge, ChallengeParticipation  # noqa: F401
    from app.models.connector import ConnectorCredential  # noqa: F401
    from app.models.notification import Notification  # noqa: F401
    from app.models.penalty import PenaltyOverride  # noqa: F401
    from app.models.sick_period import SickPeriod, SickPeriodLike  # noqa: F401
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")

    from app.routes.activities import activities_bp
    app.register_blueprint(activities_bp, url_prefix="/activities")

    from app.routes.connectors import connectors_bp
    app.register_blueprint(connectors_bp, url_prefix="/connectors")

    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from app.routes.strava_oauth import strava_oauth_bp
    app.register_blueprint(strava_oauth_bp)

    from app.routes.challenges import challenges_bp
    app.register_blueprint(challenges_bp, url_prefix="/challenges")

    from app.routes.challenge_activities import challenge_activities_bp
    app.register_blueprint(challenge_activities_bp, url_prefix="/challenge-activities")

    from app.routes.bonus import bonus_bp
    app.register_blueprint(bonus_bp, url_prefix="/bonus")

    from app.routes.dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")

    from app.routes.settings import settings_bp
    app.register_blueprint(settings_bp, url_prefix="/settings")

    from app.routes.misc import misc_bp
    app.register_blueprint(misc_bp)

    from app.routes.media import media_bp
    app.register_blueprint(media_bp, url_prefix="/media")

    from app.version import __version__

    @app.context_processor
    def inject_version():
        return {"app_version": __version__}

    @app.context_processor
    def inject_nav_challenges():
        """Stellt allen Templates die Challenge-Liste fürs Navbar-Dropdown bereit.

        'Alle sehen alles': keine User-Filterung, nur eine schlanke Query mit
        den fürs Dropdown benötigten Feldern. Nur für eingeloggte Nutzer.
        """
        from flask_login import current_user

        if not current_user.is_authenticated:
            return {"nav_challenges": []}

        from app.extensions import db
        from app.models.challenge import Challenge

        rows = db.session.execute(
            db.select(Challenge.public_id, Challenge.name).order_by(
                Challenge.created_at.desc()
            )
        ).all()
        return {
            "nav_challenges": [
                {"public_id": str(pid), "name": name} for pid, name in rows
            ]
        }

    @app.route("/")
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("auth.login"))

    return app
