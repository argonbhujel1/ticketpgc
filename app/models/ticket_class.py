from datetime import datetime, timezone
from app.extensions import db


class TicketClass(db.Model):
    __tablename__ = 'ticket_classes'
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)  # General, VIP, Premium, VVIP
    price = db.Column(db.Numeric(10, 2), nullable=False)
    total_seats = db.Column(db.Integer, default=100)
    sold = db.Column(db.Integer, default=0)
    gate = db.Column(db.String(40), default='Gate 1')
    zone = db.Column(db.String(80), default='East Stand')
    color = db.Column(db.String(20), default='#c9a227')  # gold accent per class
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def available(self):
        return max(0, (self.total_seats or 0) - (self.sold or 0))

    def __repr__(self):
        return f'<TicketClass {self.name} Rs.{self.price}>'
