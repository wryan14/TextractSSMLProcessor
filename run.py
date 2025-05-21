import os

from config import Config

def create_directories():
    """Ensure application data folders exist."""
    directories = [
        Config.PROCESSED_FOLDER,
        Config.CHUNKS_FOLDER,
        Config.UPLOAD_FOLDER,
        Config.LATIN_FOLDER,
        Config.AUDIO_OUTPUT_FOLDER,
        Config.SUBTITLE_OUTPUT,
    ]

    for path in directories:
        if not os.path.exists(path):
            os.makedirs(path)

from textract_ssml_processor import create_app


def main():
    """Run the Flask application."""
    create_directories()
    app = create_app()
    app.run(debug=True)


if __name__ == '__main__':
    main()
