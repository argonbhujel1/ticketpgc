from datetime import datetime, timezone
from app.extensions import db


class Match(db.Model):
    __tablename__ = 'matches'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    home_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    match_date = db.Column(db.DateTime, nullable=False)
    venue = db.Column(db.String(200), default='Pathari, Morang')
    venue_detail = db.Column(db.String(200), default='Domalai Rajbanshi Ground')
    status = db.Column(db.String(20), default='upcoming')  # upcoming, live, completed, cancelled
    is_featured = db.Column(db.Boolean, default=False)
    poster = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    home_team = db.relationship('Team', foreign_keys=[home_team_id])
    away_team = db.relationship('Team', foreign_keys=[away_team_id])
    ticket_classes = db.relationship('TicketClass', backref='match', lazy='dynamic')

    @property
    def display_name(self):
        h = self.home_team.short_name or self.home_team.name if self.home_team else 'TBD'
        a = self.away_team.short_name or self.away_team.name if self.away_team else 'TBD'
        return f'{h} vs {a}'

    def __repr__(self):
        return f'<Match {self.id} {self.display_name}>'
