import os
from datetime import datetime

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload settings
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
    ALLOWED_EXTENSIONS = {'zip', 'mbox'}
    
    # Google Drive settings
    GOOGLE_DRIVE_CREDENTIALS_FILE = os.path.join(basedir, 'credentials.json')
    GOOGLE_DRIVE_TOKEN_FILE = os.path.join(basedir, 'token.json')
    GOOGLE_DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
    # Application settings
    ITEMS_PER_PAGE = 20
    TIMEZONE = 'America/Toronto'