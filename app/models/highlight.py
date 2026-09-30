from datetime import datetime, timezone
from app.utils.timeutil import now_nepal_naive
from app.extensions import db


class Highlight(db.Model):
    __tablename__ = 'highlights'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default='Match Highlight')
    # YouTube 11-char id (optional if video_url set)
    youtube_id = db.Column(db.String(20), default='')
    # Cloudinary or direct video URL
    video_url = db.Column(db.String(500), default='')
    description = db.Column(db.String(500), default='')
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: now_nepal_naive())

    @property
    def has_media(self):
        return bool(self.video_url or self.youtube_id)

    def __repr__(self):
        return f'<Highlight {self.id} yt={self.youtube_id} vid={bool(self.video_url)}>'
