import os
import tempfile
from datetime import timedelta


def _database_uri():
    url = os.getenv('DATABASE_URL')
    if not url:
        if os.getenv('VERCEL'):
            db_path = os.path.join(tempfile.gettempdir(), 'skillbridge.db').replace('\\', '/')
            return f'sqlite:///{db_path}'
        return 'sqlite:///skillbridge.db'
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql+psycopg://', 1)
    if url.startswith('postgresql://'):
        return url.replace('postgresql://', 'postgresql+psycopg://', 1)
    return url


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-change-me-before-deploying')
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('COOKIE_SECURE', '0') == '1'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    WTF_CSRF_TIME_LIMIT = None
