# textract_ssml_processor/__init__.py

from flask import Flask
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    from .app import bp as app_bp
    app.register_blueprint(app_bp)

    return app
