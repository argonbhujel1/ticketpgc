from datetime import datetime
from decimal import Decimal
from app.extensions import db
from app.models.user import User
from app.models.team import Team
from app.models.match import Match
from app.models.ticket_class import TicketClass
from app.models.settings import SiteSetting
from config import Config


def seed_default_data():
    if not User.query.filter_by(username=Config.ADMIN_USERNAME).first():
        admin = User(
            username=Config.ADMIN_USERNAME,
            email='admin@patharigoldcup.com',
            full_name='Tournament Admin',
            role='admin',
            is_active=True,
        )
        admin.set_password(Config.ADMIN_PASSWORD)
        db.session.add(admin)

    if not User.query.filter_by(username='gate').first():
        gate = User(
            username='gate',
            email='gate@patharigoldcup.com',
            full_name='Gate Staff',
            role='scanner',
            is_active=True,
        )
        gate.set_password('GateScan123!')
        db.session.add(gate)

    defaults = {
        'site_name': 'Pathari Sanischare Gold Cup',
        'site_tagline': 'Football. Passion. Glory.',
        'hero_title': 'PATHARI SANISCHARE\nGOLD CUP 2026',
        'payment_esewa_enabled': 'false',
        'payment_connectips_enabled': 'false',
        'payment_qr_enabled': 'true',
        'payment_qr_image': '',
        'payment_instructions': 'Pay via QR and submit transaction ID for verification.',
        'ticket_footer_credit': 'Engineered by Argon Bhujel · Pathari Sanischare Gold Cup',
        'ticket_trophy_logo': 'logos/trophy-default.jpg',
        'ticket_background': 'backgrounds/ticket-bg-default.png',
        'site_logo': 'logos/site-logo.jpg',
        'home_background': 'backgrounds/home-bg-default.png',
    }
    for k, v in defaults.items():
        if not SiteSetting.query.filter_by(key=k).first():
            db.session.add(SiteSetting(key=k, value=v))

    if not Team.query.first():
        team_defs = [
            ('Pathari-11 Football Club', 'Pathari-11 FC', '#c62828'),
            ('United Kurseong Football Club', 'UKFC', '#1565c0'),
            ('Three Star Club', 'Three Star', '#2e7d32'),
            ('Jhapa-11 FC', 'Jhapa-11 FC', '#6a1b9a'),
            ('New Road Team', 'NRT', '#e65100'),
            ('Salhesh Yuwa Club', 'Salhesh', '#00838f'),
            ('Nepal Police Club', 'Nepal Police', '#1a237e'),
            ('Red Horse Football Club', 'Red Horse', '#b71c1c'),
            # Placeholders for knockouts (admin updates after each round)
            ('Winner of Match 1', 'Winner M1', '#c9a227'),
            ('Winner of Match 2', 'Winner M2', '#c9a227'),
            ('Winner of Match 3', 'Winner M3', '#c9a227'),
            ('Winner of Match 4', 'Winner M4', '#c9a227'),
            ('Winner of Semi-final 1', 'Winner SF1', '#ffd54f'),
            ('Winner of Semi-final 2', 'Winner SF2', '#ffd54f'),
        ]
        teams = []
        for name, short, color in team_defs:
            teams.append(Team(name=name, short_name=short, primary_color=color, is_active=True))
        db.session.add_all(teams)
        db.session.flush()
        by = {t.short_name: t for t in teams}

        venue = 'Pathari Rangashala'
        venue_detail = 'Jate Mode, Pathari · पथरी रंगशाला, जाते मोड'
        kick = 15  # 3:00 PM

        # --- 4 group / opening matches ---
        m1 = Match(
            title='Match 1 · असोज १७',
            home_team_id=by['Pathari-11 FC'].id,
            away_team_id=by['UKFC'].id,
            match_date=datetime(2026, 10, 3, kick, 0, 0),
            venue=venue, venue_detail=venue_detail,
            status='upcoming', is_featured=True,
        )
        m2 = Match(
            title='Match 2 · असोज १८',
            home_team_id=by['NRT'].id,
            away_team_id=by['Salhesh'].id,
            match_date=datetime(2026, 10, 4, kick, 0, 0),
            venue=venue, venue_detail=venue_detail,
            status='upcoming', is_featured=True,
        )
        m3 = Match(
            title='Match 3 · असोज १९',
            home_team_id=by['Three Star'].id,
            away_team_id=by['Jhapa-11 FC'].id,
            match_date=datetime(2026, 10, 5, kick, 0, 0),
            venue=venue, venue_detail=venue_detail,
            status='upcoming', is_featured=True,
        )
        m4 = Match(
            title='Match 4 · असोज २०',
            home_team_id=by['Nepal Police'].id,
            away_team_id=by['Red Horse'].id,
            match_date=datetime(2026, 10, 6, kick, 0, 0),
            venue=venue, venue_detail=venue_detail,
            status='upcoming', is_featured=True,
        )

        # --- Semi-finals ---
        sf1 = Match(
            title='Semi-final 1 · असोज २१ · Winners of Match 1 & 2',
            home_team_id=by['Winner M1'].id,
            away_team_id=by['Winner M2'].id,
            match_date=datetime(2026, 10, 7, kick, 0, 0),
            venue=venue, venue_detail=venue_detail,
            status='upcoming', is_featured=True,
        )
        sf2 = Match(
            title='Semi-final 2 · असोज २२ · Winners of Match 3 & 4',
            home_team_id=by['Winner M3'].id,
            away_team_id=by['Winner M4'].id,
            match_date=datetime(2026, 10, 8, kick, 0, 0),
            venue=venue, venue_detail=venue_detail,
            status='upcoming', is_featured=True,
        )

        # --- Final ---
        final = Match(
            title='Final · असोज २४ · Winners of Semi-final 1 & 2',
            home_team_id=by['Winner SF1'].id,
            away_team_id=by['Winner SF2'].id,
            match_date=datetime(2026, 10, 10, kick, 0, 0),
            venue=venue, venue_detail=venue_detail,
            status='upcoming', is_featured=True,
        )

        matches = [m1, m2, m3, m4, sf1, sf2, final]
        db.session.add_all(matches)
        db.session.flush()

        classes = []
        for m in matches:
            knockout = 'Semi' in (m.title or '') or 'Final' in (m.title or '')
            g_price = Decimal('500') if knockout else Decimal('300')
            v_price = Decimal('800') if knockout else Decimal('500')
            classes.extend([
                TicketClass(
                    match_id=m.id, name='General', price=g_price,
                    total_seats=400, gate='Gate 2', zone='South Stand', sort_order=1,
                ),
                TicketClass(
                    match_id=m.id, name='VIP', price=v_price,
                    total_seats=120, gate='Gate 1', zone='East Stand', sort_order=2,
                    color='#c9a227',
                ),
            ])
        db.session.add_all(classes)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
