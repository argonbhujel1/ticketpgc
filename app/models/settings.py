from datetime import datetime, timezone
from app.utils.timeutil import now_nepal_naive
from app.extensions import db


class SiteSetting(db.Model):
    __tablename__ = 'site_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=lambda: now_nepal_naive(),
                           onupdate=now_nepal_naive)

    @classmethod
    def get(cls, key, default=''):
        row = cls.query.filter_by(key=key).first()
        return row.value if row and row.value is not None else default

    @classmethod
    def set(cls, key, value):
        row = cls.query.filter_by(key=key).first()
        if row:
            row.value = value
        else:
            db.session.add(cls(key=key, value=value))
        db.session.commit()
