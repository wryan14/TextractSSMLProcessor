# textract_ssml_processor/__init__.py

from flask import Flask
from config import Config
from .timestamp import bp as timestamp_bp
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    from .app import bp as app_bp
    app.register_blueprint(app_bp)

    app.register_blueprint(timestamp_bp, url_prefix='/timestamp')

    return app
