from flask import Flask, redirect, url_for

from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

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
    }
    talisman.init_app(
        app,
        content_security_policy=csp,
        content_security_policy_nonce_in=["script-src"],
        force_https=False,
    )

    from app.models.activity import Activity  # noqa: F401 – Alembic autogenerate
    from app.models.bonus import BonusChallenge, BonusChallengeEntry  # noqa: F401
    from app.models.challenge import Challenge, ChallengeParticipation  # noqa: F401
    from app.models.connector import ConnectorCredential  # noqa: F401
    from app.models.penalty import PenaltyOverride  # noqa: F401
    from app.models.sick_week import SickWeek  # noqa: F401
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

    @app.route("/")
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("auth.login"))

    return app
