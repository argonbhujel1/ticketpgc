from datetime import datetime, timezone
from app.extensions import db


class Highlight(db.Model):
    __tablename__ = 'highlights'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default='Match Highlight')
    youtube_id = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(500), default='')
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Highlight {self.id} {self.youtube_id}>'
