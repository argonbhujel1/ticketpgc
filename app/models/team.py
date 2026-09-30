from datetime import datetime, timezone
from app.extensions import db


class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    short_name = db.Column(db.String(40))
    logo = db.Column(db.String(255))  # path under static/uploads
    primary_color = db.Column(db.String(20), default='#1a237e')
    secondary_color = db.Column(db.String(20), default='#ffffff')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Team {self.name}>'
