from datetime import datetime, timezone
from app.extensions import db


class ScanLog(db.Model):
    """Gate scan audit: valid entry or rejection."""
    __tablename__ = 'scan_logs'
    id = db.Column(db.Integer, primary_key=True)
    ticket_code = db.Column(db.String(40), index=True)
    result = db.Column(db.String(20), nullable=False)  # entered, rejected
    reason = db.Column(db.String(120))
    gate_user = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
