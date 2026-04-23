from flask import Flask

from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    from app.routes.activities import activities_bp
    app.register_blueprint(activities_bp, url_prefix="/activities")

    return app
