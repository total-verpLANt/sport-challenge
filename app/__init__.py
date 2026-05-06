import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, g, redirect, request, url_for
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config

_LOG_FORMAT = "%(asctime)s %(levelname)-5s %(name)s %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    if not app.debug:
        logging.basicConfig(
            level=logging.INFO,
            format=_LOG_FORMAT,
            datefmt=_LOG_DATE_FORMAT,
        )

    log_dir = Path(app.root_path).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "access.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
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
    from app.models.penalty import PenaltyOverride  # noqa: F401
    from app.models.sick_period import SickPeriod  # noqa: F401
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

    from app.version import __version__

    @app.context_processor
    def inject_version():
        return {"app_version": __version__}

    @app.route("/")
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("auth.login"))

    return app
