"""Separate gate staff interface: /gate/login — not mixed with admin UI."""
from datetime import datetime, timezone
from app.utils.timeutil import now_nepal_naive, format_nepal
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db, csrf
from app.models.user import User
from app.models.booking import Ticket
from app.models.scan_log import ScanLog

gate_bp = Blueprint('gate', __name__)


def _gate_stats():
    entered = ScanLog.query.filter_by(result='entered').count()
    rejected = ScanLog.query.filter_by(result='rejected').count()
    return entered, rejected


@gate_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and current_user.role in ('admin', 'scanner', 'staff'):
        return redirect(url_for('gate.index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if (user and user.check_password(request.form.get('password') or '')
                and user.is_active and user.role in ('admin', 'scanner', 'staff')):
            login_user(user, remember=True)
            return redirect(url_for('gate.index'))
        flash('Invalid gate credentials.', 'error')
    return render_template('gate/login.html')


@gate_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('gate.login'))


@gate_bp.route('/')
@login_required
def index():
    if current_user.role not in ('admin', 'scanner', 'staff'):
        flash('Gate access only.', 'error')
        return redirect(url_for('gate.login'))
    entered, rejected = _gate_stats()
    used = Ticket.query.filter_by(status='used').count()
    valid_left = Ticket.query.filter_by(status='valid').count()
    return render_template(
        'gate/index.html',
        entered=entered, rejected=rejected,
        used=used, valid_left=valid_left,
    )


@gate_bp.route('/check', methods=['POST'])
@login_required
@csrf.exempt
def check():
    if current_user.role not in ('admin', 'scanner', 'staff'):
        return jsonify({'ok': False, 'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.get_json(silent=True) or {}
    code = (data.get('code') or request.form.get('code') or '').strip().upper()
    if not code:
        return jsonify({'ok': False, 'status': 'error', 'message': 'No code'}), 400

    ticket = Ticket.query.filter_by(ticket_code=code).first()
    gate_user = current_user.username

    if not ticket:
        db.session.add(ScanLog(ticket_code=code, result='rejected', reason='not_found', gate_user=gate_user))
        db.session.commit()
        entered, rejected = _gate_stats()
        return jsonify({
            'ok': False, 'status': 'invalid', 'message': 'TICKET NOT FOUND',
            'code': code, 'entered': entered, 'rejected': rejected,
        })

    if ticket.status == 'used':
        db.session.add(ScanLog(ticket_code=code, result='rejected', reason='already_used', gate_user=gate_user))
        db.session.commit()
        entered, rejected = _gate_stats()
        return jsonify({
            'ok': False, 'status': 'used', 'message': 'ALREADY USED',
            'code': ticket.ticket_code, 'holder': ticket.holder_name,
            'checked_in_at': format_nepal(ticket.checked_in_at, '%Y-%m-%dT%H:%M:%S') if ticket.checked_in_at else None,
            'checked_in_at_display': format_nepal(ticket.checked_in_at, '%I:%M:%S %p') if ticket.checked_in_at else None,
            'match': ticket.match.display_name if ticket.match else '',
            'class': ticket.ticket_class.name if ticket.ticket_class else '',
            'entered': entered, 'rejected': rejected,
        })

    if ticket.status == 'cancelled':
        db.session.add(ScanLog(ticket_code=code, result='rejected', reason='cancelled', gate_user=gate_user))
        db.session.commit()
        entered, rejected = _gate_stats()
        return jsonify({
            'ok': False, 'status': 'cancelled', 'message': 'CANCELLED',
            'code': code, 'entered': entered, 'rejected': rejected,
        })

    ticket.status = 'used'
    ticket.checked_in_at = now_nepal_naive()
    ticket.checked_in_by = gate_user
    db.session.add(ScanLog(ticket_code=code, result='entered', reason='ok', gate_user=gate_user))
    db.session.commit()
    entered, rejected = _gate_stats()

    return jsonify({
        'ok': True, 'status': 'valid', 'message': 'VALID — ENTRY ALLOWED',
        'code': ticket.ticket_code, 'holder': ticket.holder_name,
        'match': ticket.match.display_name if ticket.match else '',
        'class': ticket.ticket_class.name if ticket.ticket_class else '',
        'checked_in_at': format_nepal(ticket.checked_in_at, '%Y-%m-%dT%H:%M:%S'),
        'checked_in_at_display': format_nepal(ticket.checked_in_at, '%I:%M:%S %p'),
        'entered': entered, 'rejected': rejected,
    })
