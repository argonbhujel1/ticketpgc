"""Separate gate staff interface: /gate/login — not mixed with admin UI."""
import re
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db, csrf
from app.models.user import User
from app.models.booking import Ticket
from app.models.scan_log import ScanLog
from app.utils.timeutil import now_nepal_naive, format_nepal

gate_bp = Blueprint('gate', __name__)


def _gate_stats():
    entered = ScanLog.query.filter_by(result='entered').count()
    rejected = ScanLog.query.filter_by(result='rejected').count()
    return entered, rejected


def _gate_label(user):
    """Name shown on scans / emails."""
    return (user.display_name or user.full_name or user.username or 'Gate').strip()


def _slug_display(name: str) -> str:
    s = (name or '').strip().lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return (s or 'staff')[:40]


def _unique_staff_username(display_name: str) -> str:
    base = 'staff_' + _slug_display(display_name)
    username = base
    n = 2
    while User.query.filter_by(username=username).first():
        username = f'{base}{n}'
        n += 1
    return username


def _make_staff_password(display_name: str) -> str:
    """Permanent password derived from display name + short secret (memorable)."""
    slug = _slug_display(display_name).replace('_', '')[:12] or 'staff'
    # e.g. argan#PGC26
    return f'{slug}#PGC26'


@gate_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and current_user.role in ('admin', 'scanner', 'staff'):
        if current_user.role == 'admin':
            return redirect(url_for('gate.register_staff'))
        return redirect(url_for('gate.index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if (user and user.check_password(request.form.get('password') or '')
                and user.is_active and user.role in ('admin', 'scanner', 'staff')):
            login_user(user, remember=True)
            if user.role == 'admin':
                return redirect(url_for('gate.register_staff'))
            return redirect(url_for('gate.index'))
        flash('Invalid gate credentials. / गेट लगइन गलत भयो।', 'error')
    return render_template('gate/login.html')


@gate_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('gate.login'))


@gate_bp.route('/register-staff', methods=['GET', 'POST'])
@login_required
def register_staff():
    """Admin (admin/admin123) registers gate staff after login."""
    if current_user.role != 'admin':
        flash('Admin only. / एडमिन मात्र।', 'error')
        return redirect(url_for('gate.index'))

    if request.method == 'POST':
        display = (request.form.get('display_name') or '').strip()
        documented = (request.form.get('documented_name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()

        if not display or len(display) < 2:
            flash('Display name required. / प्रदर्शन नाम चाहिन्छ।', 'error')
            return render_template('gate/register_staff.html')
        if not documented or len(documented) < 2:
            flash('Documented name required. / कागजातको नाम चाहिन्छ।', 'error')
            return render_template('gate/register_staff.html')
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            flash('Valid email required. / सही इमेल चाहिन्छ।', 'error')
            return render_template('gate/register_staff.html')

        username = _unique_staff_username(display)
        password = _make_staff_password(display)

        user = User(
            username=username,
            email=email,
            full_name=documented,
            display_name=display,
            documented_name=documented,
            role='scanner',
            is_active=True,
            must_change_password=False,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        mail_ok = False
        try:
            from app.services.notify import send_gate_staff_credentials_email
            mail_ok = bool(send_gate_staff_credentials_email(user, password))
        except Exception as e:
            from flask import current_app
            current_app.logger.warning('staff credentials email: %s', e)

        return render_template(
            'gate/register_done.html',
            staff=user,
            plain_password=password,
            mail_ok=mail_ok,
        )

    return render_template('gate/register_staff.html')


@gate_bp.route('/')
@login_required
def index():
    if current_user.role not in ('admin', 'scanner', 'staff'):
        flash('Gate access only.', 'error')
        return redirect(url_for('gate.login'))
    if current_user.role == 'admin':
        # Admin should register staff first; still allow open scanner
        pass
    entered, rejected = _gate_stats()
    used = Ticket.query.filter_by(status='used').count()
    valid_left = Ticket.query.filter_by(status='valid').count()
    from app.models.settings import SiteSetting
    voice_lang = (SiteSetting.get('gate_voice_lang', 'en') or 'en').strip().lower()
    if voice_lang not in ('en', 'ne'):
        voice_lang = 'en'
    return render_template(
        'gate/index.html',
        entered=entered, rejected=rejected,
        used=used, valid_left=valid_left,
        voice_lang=voice_lang,
        gate_label=_gate_label(current_user),
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
    gate_user = _gate_label(current_user)

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
    try:
        from app.services.notify import send_ticket_used_email
        send_ticket_used_email(ticket)
    except Exception as e:
        from flask import current_app
        current_app.logger.warning('ticket used email: %s', e)
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
