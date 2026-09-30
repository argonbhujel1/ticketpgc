from datetime import datetime, timezone
from app.extensions import db
import secrets


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    booking_code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    ticket_class_id = db.Column(db.Integer, db.ForeignKey('ticket_classes.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    buyer_name = db.Column(db.String(120), nullable=False)
    buyer_phone = db.Column(db.String(30), nullable=False)
    buyer_email = db.Column(db.String(120))
    payment_method = db.Column(db.String(40))  # esewa, connectips, qr, manual
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, failed, refunded, rejected
    payment_ref = db.Column(db.String(120))
    payment_proof = db.Column(db.String(255))  # uploads/proofs/...
    notes = db.Column(db.Text)
    rejection_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    paid_at = db.Column(db.DateTime)
    rejected_at = db.Column(db.DateTime)

    match = db.relationship('Match')
    ticket_class = db.relationship('TicketClass')
    tickets = db.relationship('Ticket', backref='booking', lazy='dynamic')

    @staticmethod
    def generate_code():
        year = datetime.now().year
        return f'PGC-BOOK-{year}-{secrets.token_hex(3).upper()}'


class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    ticket_code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    ticket_class_id = db.Column(db.Integer, db.ForeignKey('ticket_classes.id'), nullable=False)
    holder_name = db.Column(db.String(120))
    status = db.Column(db.String(20), default='valid')  # valid, used, cancelled
    checked_in_at = db.Column(db.DateTime)
    checked_in_by = db.Column(db.String(80))
    qr_payload = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    match = db.relationship('Match')
    ticket_class = db.relationship('TicketClass')

    @staticmethod
    def generate_code(seq=None):
        year = datetime.now().year
        if seq is not None:
            return f'PGC-TKT-{year}-{seq:06d}'
        return f'PGC-TKT-{year}-{secrets.token_hex(3).upper()}'
