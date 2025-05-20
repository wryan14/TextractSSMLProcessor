import os

def create_directories():
    # Get the directory of the current script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    directories = ["processed", "chunks", "uploads"]
    for directory in directories:
        path = os.path.join(base_dir, directory)
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
