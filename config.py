import os
from pathlib import Path
from datetime import timedelta

basedir = Path(__file__).parent.absolute()
ON_VERCEL = bool(os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV'))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'pgc-dev-secret-change-in-production-2026'
    _db = os.environ.get('DATABASE_URL') or f'sqlite:///{basedir / "instance" / "pgc.db"}'
    if _db.startswith('postgres://'):
        _db = _db.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Serverless (Vercel): no persistent connections — NullPool
    if ON_VERCEL:
        from sqlalchemy.pool import NullPool
        _engine_opts = {
            'poolclass': NullPool,
            'pool_pre_ping': True,
        }
        if _db.startswith('postgresql'):
            _engine_opts['connect_args'] = {'connect_timeout': 10}
        SQLALCHEMY_ENGINE_OPTIONS = _engine_opts
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 5,
            'max_overflow': 2,
        }

    UPLOAD_FOLDER = basedir / 'app' / 'static' / 'uploads'
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Secure cookies on HTTPS (Vercel)
    SESSION_COOKIE_SECURE = ON_VERCEL or os.environ.get('SESSION_COOKIE_SECURE', '').lower() in ('1', 'true', 'yes')
    WTF_CSRF_ENABLED = True
    SITE_NAME = 'Pathari Gold Cup'
    SITE_YEAR = '2026'
    SITE_FULL = 'Pathari Gold Cup 2026'
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'ChangeMeNow123!')


config = {
    'development': Config,
    'production': Config,
    'default': Config,
}
