import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    PROCESSED_FOLDER = os.path.join(os.getcwd(), 'processed')
    CHUNKS_FOLDER = os.path.join(os.getcwd(), 'chunks')
    LATIN_FOLDER = os.path.join(os.getcwd(), 'latin')
    AUDIO_OUTPUT_FOLDER = os.path.join(os.getcwd(), 'audio')
