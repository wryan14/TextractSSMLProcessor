# textract_ssml_processor/__init__.py

from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your_secret_key'
    app.config['UPLOAD_FOLDER'] = 'uploads/'

    from .app import bp as app_bp
    app.register_blueprint(app_bp)

    return app
