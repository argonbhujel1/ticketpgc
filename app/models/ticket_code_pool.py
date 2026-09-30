"""Recycled ticket codes available for re-issue after deletion."""
from datetime import datetime, timezone
from app.utils.timeutil import now_nepal_naive
from app.extensions import db


class TicketCodePool(db.Model):
    __tablename__ = 'ticket_code_pool'
    id = db.Column(db.Integer, primary_key=True)
    ticket_code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    freed_at = db.Column(db.DateTime, default=lambda: now_nepal_naive())
    previous_holder = db.Column(db.String(120))
    previous_email = db.Column(db.String(120))
