import os
from pathlib import Path
from flask import Flask, render_template
from config import config
from app.extensions import db, login_manager, csrf

_DB_READY = False


def _ensure_schema(app):
    """Add columns that create_all will not alter on existing Postgres tables."""
    from sqlalchemy import text
    stmts = [
        "ALTER TABLE highlights ADD COLUMN IF NOT EXISTS video_url VARCHAR(500) DEFAULT ''",
        "ALTER TABLE highlights ALTER COLUMN youtube_id DROP NOT NULL",
        "ALTER TABLE highlights ALTER COLUMN youtube_id SET DEFAULT ''",
        "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS rejection_reason TEXT",
        "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMP WITHOUT TIME ZONE",
    ]
    with db.engine.begin() as conn:
        for s in stmts:
            try:
                conn.execute(text(s))
            except Exception as e:
                app.logger.debug('schema skip %s: %s', s[:40], e)


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    _app_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(_app_dir / 'templates'),
        static_folder=str(_app_dir / 'static'),
    )
    app.config.from_object(config.get(config_name, config['default']))

    on_vercel = bool(os.environ.get('VERCEL'))
    if on_vercel:
        app.config['UPLOAD_FOLDER'] = Path('/tmp/pgc_uploads')
    else:
        app.config['UPLOAD_FOLDER'] = Path(app.config['UPLOAD_FOLDER'])

    for sub in ['logos', 'posters', 'qr', 'tickets', 'proofs', 'backgrounds', 'highlights']:
        try:
            (Path(app.config['UPLOAD_FOLDER']) / sub).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    try:
        (_app_dir.parent / 'instance').mkdir(exist_ok=True)
    except OSError:
        pass

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.routes.public import public_bp
    from app.routes.admin import admin_bp
    from app.routes.scanner import scanner_bp
    from app.routes.gate import gate_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(scanner_bp, url_prefix='/scanner')
    app.register_blueprint(gate_bp, url_prefix='/gate')

    @app.context_processor
    def inject_globals():
        from app.models.settings import SiteSetting
        from config import Config

        def get_setting(key, default=''):
            try:
                return SiteSetting.get(key, default)
            except Exception:
                return default

        return {
            'site_name': get_setting('site_name', Config.SITE_NAME),
            'site_tagline': get_setting('site_tagline', 'Football. Passion. Glory.'),
            'site_year': Config.SITE_YEAR,
            'get_setting': get_setting,
        }

    @app.context_processor
    def inject_branding():
        from app.models.settings import SiteSetting
        from flask import url_for

        def media_url(rel):
            if not rel:
                return None
            # Cloudinary / absolute URL stored in DB
            if str(rel).startswith('http://') or str(rel).startswith('https://'):
                return rel
            try:
                return url_for('public.media', filename=rel)
            except Exception:
                return None

        def team_logo_url(team):
            if team and getattr(team, 'logo', None):
                return media_url(team.logo)
            return None

        try:
            site_logo = SiteSetting.get('site_logo', '')
        except Exception:
            site_logo = ''
        return {
            'site_logo_rel': site_logo,
            'site_logo_url': media_url(site_logo) if site_logo else None,
            'team_logo_url': team_logo_url,
            'media_url': media_url,
            'get_setting': SiteSetting.get,
        }

    @app.errorhandler(404)
    def not_found(e):
        try:
            return render_template('public/error.html', code=404, message='Page not found'), 404
        except Exception:
            return ('<h1>404</h1><p>Page not found</p>', 404)

    @app.errorhandler(500)
    def server_error(e):
        try:
            return render_template('public/error.html', code=500, message='Something went wrong'), 500
        except Exception:
            return ('<h1>500</h1><p>Something went wrong</p>', 500)

    # Run DB bootstrap at most once per serverless instance (not every request)
    global _DB_READY
    if not _DB_READY:
        with app.app_context():
            try:
                from sqlalchemy import inspect
                insp = inspect(db.engine)
                need_create = not insp.has_table('users')
                if need_create:
                    db.create_all()
                elif not insp.has_table('highlights'):
                    db.create_all()  # only if new tables missing
            except Exception as e:
                app.logger.warning('DB create_all: %s', e)
            try:
                _ensure_schema(app)
            except Exception as e:
                app.logger.warning('schema ensure: %s', e)
            # Seed only when admin missing (fast path: 1 query)
            try:
                from app.models.user import User
                from config import Config
                if not User.query.filter_by(username=Config.ADMIN_USERNAME).first():
                    from app.services.seed import seed_default_data
                    seed_default_data()
            except Exception as e:
                app.logger.warning('DB seed deferred: %s', e)
        _DB_READY = True

    return app
