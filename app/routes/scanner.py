from datetime import datetime, timezone
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db, csrf
from app.models.booking import Ticket

scanner_bp = Blueprint('scanner', __name__)


@scanner_bp.route('/')
@login_required
def index():
    scanned = Ticket.query.filter(Ticket.checked_in_at.isnot(None)).count()
    valid_left = Ticket.query.filter_by(status='valid').count()
    used = Ticket.query.filter_by(status='used').count()
    return render_template('scanner/index.html', scanned=scanned, valid_left=valid_left, used=used)


@scanner_bp.route('/check', methods=['POST'])
@login_required
@csrf.exempt  # scanner may post from camera JS; still requires login session
def check():
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or request.form.get('code') or '').strip().upper()
    if not code:
        return jsonify({'ok': False, 'status': 'error', 'message': 'No code'}), 400

    ticket = Ticket.query.filter_by(ticket_code=code).first()
    if not ticket:
        return jsonify({'ok': False, 'status': 'invalid', 'message': 'Ticket not found', 'code': code})

    if ticket.status == 'used':
        return jsonify({
            'ok': False,
            'status': 'used',
            'message': 'Already checked in',
            'code': ticket.ticket_code,
            'holder': ticket.holder_name,
            'checked_in_at': ticket.checked_in_at.isoformat() if ticket.checked_in_at else None,
            'match': ticket.match.display_name if ticket.match else '',
            'class': ticket.ticket_class.name if ticket.ticket_class else '',
        })

    if ticket.status == 'cancelled':
        return jsonify({'ok': False, 'status': 'cancelled', 'message': 'Ticket cancelled', 'code': code})

    ticket.status = 'used'
    ticket.checked_in_at = datetime.now(timezone.utc)
    ticket.checked_in_by = current_user.username if current_user.is_authenticated else 'scanner'
    db.session.commit()

    return jsonify({
        'ok': True,
        'status': 'valid',
        'message': 'VALID TICKET',
        'code': ticket.ticket_code,
        'holder': ticket.holder_name,
        'match': ticket.match.display_name if ticket.match else '',
        'class': ticket.ticket_class.name if ticket.ticket_class else '',
        'checked_in_at': ticket.checked_in_at.isoformat(),
    })
