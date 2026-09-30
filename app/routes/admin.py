from datetime import datetime, timezone
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models.user import User
from app.models.team import Team
from app.models.match import Match
from app.models.ticket_class import TicketClass
from app.models.booking import Booking, Ticket
from app.models.settings import SiteSetting
from app.models.highlight import Highlight
from app.services.uploads import save_upload
from app.services.notify import notify_tickets_issued, send_ticket_invalidated_email
from app.services.ticket_codes import allocate_ticket_code, recycle_ticket_code
from flask import send_from_directory, current_app
from pathlib import Path as PathLib

admin_bp = Blueprint('admin', __name__)

def _recalc_class_sold(*class_ids):
    """Recompute TicketClass.sold from actual tickets after deletes."""
    ids = {i for i in class_ids if i}
    for cid in ids:
        tc = TicketClass.query.get(cid)
        if not tc:
            continue
        tc.sold = Ticket.query.filter_by(ticket_class_id=cid).count()





def _delete_tickets_by_ids(ids):
    n = 0
    class_ids = set()
    for i in ids:
        tk = Ticket.query.get(i)
        if not tk:
            continue
        class_ids.add(tk.ticket_class_id)
        code = tk.ticket_code
        holder = tk.holder_name
        email = None
        if tk.booking:
            email = tk.booking.buyer_email
            holder = holder or tk.booking.buyer_name
        try:
            send_ticket_invalidated_email(code, holder, email)
        except Exception as e:
            current_app.logger.warning('invalidate mail: %s', e)
        recycle_ticket_code(code, holder=holder, email=email)
        db.session.delete(tk)
        n += 1
    _recalc_class_sold(*class_ids)
    return n


def _delete_bookings_by_ids(ids):
    n = 0
    class_ids = set()
    for i in ids:
        b = Booking.query.get(i)
        if not b:
            continue
        if b.ticket_class_id:
            class_ids.add(b.ticket_class_id)
        for tk in Ticket.query.filter_by(booking_id=b.id).all():
            class_ids.add(tk.ticket_class_id)
            try:
                send_ticket_invalidated_email(
                    tk.ticket_code, tk.holder_name or b.buyer_name, b.buyer_email
                )
            except Exception:
                pass
            recycle_ticket_code(tk.ticket_code, holder=b.buyer_name, email=b.buyer_email)
            db.session.delete(tk)
        db.session.delete(b)
        n += 1
    _recalc_class_sold(*class_ids)
    return n


def _delete_classes_by_ids(ids, force=False):
    deleted = skipped = 0
    for i in ids:
        tc = TicketClass.query.get(i)
        if not tc:
            continue
        used = Ticket.query.filter_by(ticket_class_id=tc.id).count()
        if used and not force:
            skipped += 1
            continue
        if force:
            Ticket.query.filter_by(ticket_class_id=tc.id).delete()
            Booking.query.filter_by(ticket_class_id=tc.id).delete()
        db.session.delete(tc)
        deleted += 1
    return deleted, skipped


def _delete_matches_by_ids(ids):
    n = 0
    for i in ids:
        m = Match.query.get(i)
        if not m:
            continue
        # cascade related
        tcs = TicketClass.query.filter_by(match_id=m.id).all()
        for tc in tcs:
            Ticket.query.filter_by(ticket_class_id=tc.id).delete()
            Booking.query.filter_by(ticket_class_id=tc.id).delete()
            db.session.delete(tc)
        Ticket.query.filter_by(match_id=m.id).delete()
        Booking.query.filter_by(match_id=m.id).delete()
        db.session.delete(m)
        n += 1
    return n


def _delete_teams_by_ids(ids):
    deleted = skipped = 0
    for i in ids:
        team = Team.query.get(i)
        if not team:
            continue
        used = Match.query.filter(
            (Match.home_team_id == team.id) | (Match.away_team_id == team.id)
        ).count()
        if used:
            skipped += 1
            continue
        db.session.delete(team)
        deleted += 1
    return deleted, skipped


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password') or '') and user.is_active:
            login_user(user, remember=True)
            return redirect(url_for('admin.dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('admin/login.html')


@admin_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('admin.login'))


@admin_bp.route('/')
@login_required
def dashboard():
    bookings = Booking.query.count()
    paid = Booking.query.filter_by(payment_status='paid').count()
    tickets = Ticket.query.count()
    checked = Ticket.query.filter_by(status='used').count()
    revenue = db.session.query(db.func.coalesce(db.func.sum(Booking.total_amount), 0))\
        .filter_by(payment_status='paid').scalar()
    pending = Booking.query.filter_by(payment_status='pending').count()
    recent = Booking.query.order_by(Booking.created_at.desc()).limit(8).all()
    return render_template(
        'admin/dashboard.html',
        bookings=bookings, paid=paid, tickets=tickets, checked=checked,
        revenue=revenue, pending=pending, recent=recent,
    )


@admin_bp.route('/matches')
@login_required
def matches():
    items = Match.query.order_by(Match.match_date.desc()).all()
    return render_template('admin/matches.html', matches=items)


@admin_bp.route('/matches/new', methods=['GET', 'POST'])
@login_required
def match_new():
    teams = Team.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        try:
            dt = datetime.strptime(request.form['match_date'], '%Y-%m-%dT%H:%M')
        except Exception:
            flash('Invalid date.', 'error')
            return render_template('admin/match_form.html', teams=teams, match=None)
        m = Match(
            title=request.form.get('title') or None,
            home_team_id=int(request.form['home_team_id']),
            away_team_id=int(request.form['away_team_id']),
            match_date=dt,
            venue=request.form.get('venue') or 'Pathari, Morang',
            venue_detail=request.form.get('venue_detail') or '',
            status=request.form.get('status') or 'upcoming',
            is_featured=bool(request.form.get('is_featured')),
        )
        db.session.add(m)
        db.session.commit()
        flash('Match created.', 'success')
        return redirect(url_for('admin.matches'))
    return render_template('admin/match_form.html', teams=teams, match=None)




@admin_bp.route('/matches/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def match_edit(id):
    match = Match.query.get_or_404(id)
    teams = Team.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        try:
            dt = datetime.strptime(request.form['match_date'], '%Y-%m-%dT%H:%M')
        except Exception:
            flash('Invalid date.', 'error')
            return render_template('admin/match_form.html', teams=teams, match=match)
        match.title = request.form.get('title') or None
        match.home_team_id = int(request.form['home_team_id'])
        match.away_team_id = int(request.form['away_team_id'])
        match.match_date = dt
        match.venue = request.form.get('venue') or match.venue
        match.venue_detail = request.form.get('venue_detail') or ''
        match.status = request.form.get('status') or match.status
        match.is_featured = bool(request.form.get('is_featured'))
        db.session.commit()
        flash('Match updated.', 'success')
        return redirect(url_for('admin.matches'))
    return render_template('admin/match_form.html', teams=teams, match=match)

@admin_bp.route('/teams')
@login_required
def teams():
    items = Team.query.order_by(Team.name).all()
    return render_template('admin/teams.html', teams=items)


@admin_bp.route('/teams/new', methods=['GET', 'POST'])
@login_required
def team_new():
    if request.method == 'POST':
        team = Team(
            name=request.form['name'].strip(),
            short_name=request.form.get('short_name') or request.form['name'].strip()[:20],
            primary_color=request.form.get('primary_color') or '#1a237e',
        )
        f = request.files.get('logo')
        if f and f.filename:
            path = save_upload(f, folder='logos')
            if path:
                team.logo = path
        db.session.add(team)
        db.session.commit()
        flash('Team added.', 'success')
        return redirect(url_for('admin.teams'))
    return render_template('admin/team_form.html', team=None)


@admin_bp.route('/teams/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def team_edit(id):
    team = Team.query.get_or_404(id)
    if request.method == 'POST':
        team.name = request.form['name'].strip()
        team.short_name = request.form.get('short_name') or team.name[:20]
        team.primary_color = request.form.get('primary_color') or team.primary_color
        f = request.files.get('logo')
        if f and f.filename:
            path = save_upload(f, folder='logos')
            if path:
                team.logo = path
        db.session.commit()
        flash('Team updated (logo saved if uploaded).', 'success')
        return redirect(url_for('admin.teams'))
    return render_template('admin/team_form.html', team=team)


@admin_bp.route('/classes')
@login_required
def classes():
    items = TicketClass.query.order_by(TicketClass.match_id, TicketClass.sort_order).all()
    matches = Match.query.all()
    return render_template('admin/classes.html', classes=items, matches=matches)




@admin_bp.route('/classes/bulk-delete', methods=['POST'])
@login_required
def class_bulk_delete():
    ids = request.form.getlist('class_ids')
    if not ids:
        flash('Select at least one ticket class.', 'error')
        return redirect(url_for('admin.classes'))
    deleted = 0
    skipped = 0
    for sid in ids:
        try:
            tc = TicketClass.query.get(int(sid))
        except Exception:
            continue
        if not tc:
            continue
        # Don't delete if tickets already sold against this class
        from app.models.booking import Ticket
        used = Ticket.query.filter_by(ticket_class_id=tc.id).count()
        if used > 0 or (tc.sold or 0) > 0:
            skipped += 1
            continue
        db.session.delete(tc)
        deleted += 1
    db.session.commit()
    msg = f'Deleted {deleted} ticket class(es).'
    if skipped:
        msg += f' Skipped {skipped} (already has sold tickets).'
    flash(msg, 'success' if deleted else 'error')
    return redirect(url_for('admin.classes'))

@admin_bp.route('/classes/new', methods=['POST'])
@login_required
def class_new():
    tc = TicketClass(
        match_id=int(request.form['match_id']),
        name=request.form['name'].strip(),
        price=Decimal(request.form['price']),
        total_seats=int(request.form.get('total_seats') or 100),
        gate=request.form.get('gate') or 'Gate 1',
        zone=request.form.get('zone') or 'East Stand',
        sort_order=int(request.form.get('sort_order') or 0),
    )
    db.session.add(tc)
    db.session.commit()
    flash('Ticket class created.', 'success')
    return redirect(url_for('admin.classes'))




@admin_bp.route('/classes/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def class_edit(id):
    tc = TicketClass.query.get_or_404(id)
    matches = Match.query.order_by(Match.match_date.desc()).all()
    if request.method == 'POST':
        tc.match_id = int(request.form['match_id'])
        tc.name = request.form['name'].strip()
        tc.price = __import__('decimal').Decimal(request.form['price'])
        tc.total_seats = int(request.form.get('total_seats') or tc.total_seats or 100)
        tc.gate = request.form.get('gate') or 'Gate 1'
        tc.zone = request.form.get('zone') or 'East Stand'
        tc.sort_order = int(request.form.get('sort_order') or 0)
        tc.is_active = bool(request.form.get('is_active', True))
        db.session.commit()
        flash('Ticket class updated.', 'success')
        return redirect(url_for('admin.classes'))
    return render_template('admin/class_form.html', tc=tc, matches=matches)

@admin_bp.route('/bookings')
@login_required
def bookings():
    status = request.args.get('status', '')
    q = Booking.query
    if status:
        q = q.filter_by(payment_status=status)
    items = q.order_by(Booking.created_at.desc()).limit(100).all()
    return render_template('admin/bookings.html', bookings=items, status=status)


@admin_bp.route('/bookings/<int:id>/confirm', methods=['POST'])
@login_required
def booking_confirm(id):
    booking = Booking.query.get_or_404(id)
    if booking.payment_status != 'paid':
        booking.payment_status = 'paid'
        booking.paid_at = datetime.now(timezone.utc)
        booking.payment_ref = booking.payment_ref or request.form.get('payment_ref') or 'MANUAL'
        existing = Ticket.query.filter_by(booking_id=booking.id).count()
        if existing == 0:
            for i in range(booking.quantity):
                code = allocate_ticket_code()
                db.session.add(Ticket(
                    ticket_code=code,
                    booking_id=booking.id,
                    match_id=booking.match_id,
                    ticket_class_id=booking.ticket_class_id,
                    holder_name=booking.buyer_name,
                    status='valid',
                    qr_payload=code,
                ))
            tc = booking.ticket_class
            if tc:
                tc.sold = (tc.sold or 0) + booking.quantity
        db.session.commit()
        issued = Ticket.query.filter_by(booking_id=booking.id).all()
        result = {'sms': False, 'email': False, 'sms_error': '', 'email_error': ''}
        try:
            result = notify_tickets_issued(booking, issued) or result
        except Exception as e:
            current_app.logger.warning('Notify failed: %s', e)
            result['email_error'] = str(e)
        if result.get('email'):
            flash('Payment confirmed. Ticket email sent (PNG attached).', 'success')
        else:
            flash('Payment confirmed, tickets issued. Email FAILED — need buyer email + MAIL_* on Vercel.', 'error')
    return redirect(url_for('admin.booking_detail', id=booking.id))


@admin_bp.route('/bookings/<int:id>/reject', methods=['POST'])
@login_required
def booking_reject(id):
    booking = Booking.query.get_or_404(id)
    if booking.payment_status == 'paid':
        flash('Cannot reject a paid booking. Delete tickets first if needed.', 'error')
        return redirect(url_for('admin.booking_detail', id=booking.id))
    reason = (request.form.get('rejection_reason') or '').strip()
    if not reason:
        flash('Please enter a rejection reason.', 'error')
        return redirect(url_for('admin.booking_detail', id=booking.id))
    booking.payment_status = 'rejected'
    booking.rejection_reason = reason[:1000]
    booking.rejected_at = datetime.now(timezone.utc)
    # cancel any accidental tickets (should be none if not paid)
    for tk in Ticket.query.filter_by(booking_id=booking.id).all():
        tk.status = 'cancelled'
    db.session.commit()
    # optional email
    try:
        from app.services.notify import send_booking_rejected_email
        send_booking_rejected_email(booking)
    except Exception as e:
        current_app.logger.warning('reject mail: %s', e)
    flash('Booking rejected. Reason saved.', 'success')
    return redirect(url_for('admin.booking_detail', id=booking.id))


@admin_bp.route('/bookings/<int:id>/resend', methods=['POST'])
@login_required
def booking_resend(id):
    booking = Booking.query.get_or_404(id)
    issued = Ticket.query.filter_by(booking_id=booking.id).all()
    if not issued:
        flash('No tickets to send. Confirm payment first.', 'error')
        return redirect(url_for('admin.booking_detail', id=id))
    try:
        result = notify_tickets_issued(booking, issued)
        flash(
            f"Resend email: {'OK' if result.get('email') else 'FAIL'}. "
            f"To={booking.buyer_email or '(no email on booking)'}",
            'success' if result.get('email') else 'error'
        )
    except Exception as e:
        flash(f'Resend error: {e}', 'error')
    return redirect(url_for('admin.booking_detail', id=id))


@admin_bp.route('/tickets')
@login_required
def tickets():
    items = Ticket.query.order_by(Ticket.created_at.desc()).limit(100).all()
    return render_template('admin/tickets.html', tickets=items)




@admin_bp.route('/teams/<int:id>/delete', methods=['POST'])
@login_required
def team_delete(id):
    deleted, skipped = _delete_teams_by_ids([id])
    db.session.commit()
    if deleted:
        flash('Team deleted.', 'success')
    else:
        flash('Cannot delete: team is used in a match. Delete/edit those matches first.', 'error')
    return redirect(url_for('admin.teams'))


@admin_bp.route('/teams/bulk-delete', methods=['POST'])
@login_required
def team_bulk_delete():
    ids = [int(x) for x in request.form.getlist('ids') if str(x).isdigit()]
    deleted, skipped = _delete_teams_by_ids(ids)
    db.session.commit()
    flash(f'Teams deleted: {deleted}. Skipped (in matches): {skipped}.', 'success' if deleted else 'error')
    return redirect(url_for('admin.teams'))


@admin_bp.route('/matches/<int:id>/delete', methods=['POST'])
@login_required
def match_delete(id):
    n = _delete_matches_by_ids([id])
    db.session.commit()
    flash('Match and related classes/bookings/tickets deleted.' if n else 'Match not found.', 'success' if n else 'error')
    return redirect(url_for('admin.matches'))


@admin_bp.route('/matches/bulk-delete', methods=['POST'])
@login_required
def match_bulk_delete():
    ids = [int(x) for x in request.form.getlist('ids') if str(x).isdigit()]
    n = _delete_matches_by_ids(ids)
    db.session.commit()
    flash(f'Deleted {n} match(es) and related data.', 'success' if n else 'error')
    return redirect(url_for('admin.matches'))


@admin_bp.route('/classes/<int:id>/delete', methods=['POST'])
@login_required
def class_delete(id):
    force = request.form.get('force') == '1'
    deleted, skipped = _delete_classes_by_ids([id], force=force)
    db.session.commit()
    if deleted:
        flash('Ticket class deleted.', 'success')
    else:
        flash('Class has sold tickets. Use force delete from bulk with care, or delete bookings first.', 'error')
    return redirect(url_for('admin.classes'))


@admin_bp.route('/bookings/<int:id>/delete', methods=['POST'])
@login_required
def booking_delete(id):
    n = _delete_bookings_by_ids([id])
    db.session.commit()
    flash('Booking and its tickets deleted.' if n else 'Not found.', 'success' if n else 'error')
    return redirect(url_for('admin.bookings'))


@admin_bp.route('/bookings/bulk-delete', methods=['POST'])
@login_required
def booking_bulk_delete():
    ids = [int(x) for x in request.form.getlist('ids') if str(x).isdigit()]
    n = _delete_bookings_by_ids(ids)
    db.session.commit()
    flash(f'Deleted {n} booking(s).', 'success' if n else 'error')
    return redirect(url_for('admin.bookings'))


@admin_bp.route('/tickets/<int:id>/delete', methods=['POST'])
@login_required
def ticket_delete(id):
    n = _delete_tickets_by_ids([id])
    db.session.commit()
    flash('Ticket deleted.' if n else 'Not found.', 'success' if n else 'error')
    return redirect(url_for('admin.tickets'))


@admin_bp.route('/tickets/bulk-delete', methods=['POST'])
@login_required
def ticket_bulk_delete():
    ids = [int(x) for x in request.form.getlist('ids') if str(x).isdigit()]
    n = _delete_tickets_by_ids(ids)
    db.session.commit()
    flash(f'Deleted {n} ticket(s).', 'success' if n else 'error')
    return redirect(url_for('admin.tickets'))


@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    keys = [
        'site_name', 'site_tagline', 'hero_title',
        'payment_esewa_enabled', 'payment_connectips_enabled', 'payment_qr_enabled',
        'payment_instructions', 'payment_qr_image', 'ticket_background', 'ticket_qr_background', 'ticket_footer_credit',
        'home_background', 'ticket_trophy_logo', 'site_logo', 'highlight_youtube',
    ]
    if request.method == 'POST':
        for k in keys:
            if k in request.form and k != 'payment_qr_image' and k != 'highlight_youtube':
                SiteSetting.set(k, request.form.get(k))
        from app.services.cloudinary_store import youtube_id_from_url
        yt_raw = (request.form.get('highlight_youtube') or '').strip()
        SiteSetting.set('highlight_youtube', youtube_id_from_url(yt_raw) if yt_raw else '')
        # QR image upload
        f = request.files.get('payment_qr_file')
        if f and f.filename:
            path = save_upload(f, folder='qr')
            if path:
                SiteSetting.set('payment_qr_image', path)
                flash('Payment QR image uploaded.', 'success')
            else:
                flash('Invalid QR image (use png/jpg/webp).', 'error')
        bg = request.files.get('ticket_background_file')
        if bg and bg.filename:
            path = save_upload(bg, folder='backgrounds')
            if path:
                SiteSetting.set('ticket_background', path)
                flash('Ticket background uploaded.' + (
                    ' (Cloudinary)' if str(path).startswith('http') else ''
                ), 'success')
            else:
                flash(
                    'Ticket background upload failed. On Vercel set CLOUDINARY_* env vars '
                    'and use png/jpg/webp under 8MB.',
                    'error',
                )
        qr_bg = request.files.get('ticket_qr_background_file')
        if qr_bg and qr_bg.filename:
            path = save_upload(qr_bg, folder='backgrounds')
            if path:
                SiteSetting.set('ticket_qr_background', path)
                flash('QR panel background uploaded.' + (
                    ' (Cloudinary)' if str(path).startswith('http') else ''
                ), 'success')
            else:
                flash('QR background upload failed. Need CLOUDINARY_* on Vercel.', 'error')
        if request.form.get('clear_ticket_qr_background'):
            SiteSetting.set('ticket_qr_background', '')
            flash('QR panel background cleared.', 'success')
        home_bg = request.files.get('home_background_file')
        if home_bg and home_bg.filename:
            path = save_upload(home_bg, folder='backgrounds')
            if path:
                SiteSetting.set('home_background', path)
                flash('Homepage background uploaded.', 'success')
        trophy = request.files.get('ticket_trophy_file')
        if trophy and trophy.filename:
            path = save_upload(trophy, folder='logos', clear_bg=True)
            if path:
                SiteSetting.set('ticket_trophy_logo', path)
                flash('Trophy / strip logo uploaded.', 'success')
        site_logo = request.files.get('site_logo_file')
        if site_logo and site_logo.filename:
            path = save_upload(site_logo, folder='logos', clear_bg=True)
            if path:
                SiteSetting.set('site_logo', path)
                flash('Website logo uploaded.', 'success')
        yt_raw = (request.form.get('highlight_youtube') or '').strip()
        from app.services.cloudinary_store import youtube_id_from_url
        SiteSetting.set('highlight_youtube', youtube_id_from_url(yt_raw) if yt_raw else '')

        flash('Settings saved.', 'success')
        return redirect(url_for('admin.settings'))
    values = {k: SiteSetting.get(k, '') for k in keys}
    return render_template('admin/settings.html', values=values)


@admin_bp.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    """Serve upload files (QR, payment proofs) for admin."""
    if filename.startswith('http://') or filename.startswith('https://'):
        return redirect(filename)
    if 'res.cloudinary.com' in filename:
        return redirect('https://' + filename.lstrip('/'))
    root = PathLib(current_app.config['UPLOAD_FOLDER'])
    return send_from_directory(root, filename)


@admin_bp.route('/bookings/<int:id>')
@login_required
def booking_detail(id):
    booking = Booking.query.get_or_404(id)
    tickets = Ticket.query.filter_by(booking_id=booking.id).all()
    return render_template('admin/booking_detail.html', booking=booking, tickets=tickets)


# ── Highlights (YouTube videos on homepage) ──────────────────────────

@admin_bp.route('/highlights')
@login_required
def highlights():
    items = Highlight.query.order_by(Highlight.sort_order.asc(), Highlight.id.desc()).all()
    return render_template('admin/highlights.html', items=items)


@admin_bp.route('/highlights/new', methods=['GET', 'POST'])
@login_required
def highlight_new():
    if request.method == 'POST':
        from app.services.cloudinary_store import youtube_id_from_url
        from app.services.uploads import save_upload
        yt_raw = (request.form.get('youtube_url') or '').strip()
        yt_id = youtube_id_from_url(yt_raw) if yt_raw else ''
        video_url = ''
        f = request.files.get('video_file')
        if f and f.filename:
            video_url = save_upload(f, folder='highlights', resource_type='video') or ''
        if not yt_id and not video_url:
            flash('YouTube link/embed or video file required.', 'error')
            return render_template('admin/highlight_form.html', item=None)
        h = Highlight(
            title=(request.form.get('title') or 'Match Highlight').strip()[:200],
            youtube_id=yt_id or '',
            video_url=video_url or '',
            description=(request.form.get('description') or '').strip()[:500],
            sort_order=int(request.form.get('sort_order') or 0),
            is_active=bool(request.form.get('is_active')),
        )
        db.session.add(h)
        db.session.commit()
        flash('Highlight added.', 'success')
        return redirect(url_for('admin.highlights'))
    return render_template('admin/highlight_form.html', item=None)


@admin_bp.route('/highlights/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def highlight_edit(id):
    item = Highlight.query.get_or_404(id)
    if request.method == 'POST':
        from app.services.cloudinary_store import youtube_id_from_url
        from app.services.uploads import save_upload
        yt_raw = (request.form.get('youtube_url') or '').strip()
        yt_id = youtube_id_from_url(yt_raw) if yt_raw else (item.youtube_id or '')
        video_url = item.video_url or ''
        f = request.files.get('video_file')
        if f and f.filename:
            uploaded = save_upload(f, folder='highlights', resource_type='video')
            if uploaded:
                video_url = uploaded
        # clear video if requested
        if request.form.get('clear_video'):
            video_url = ''
        if not yt_id and not video_url:
            flash('YouTube link/embed or video file required.', 'error')
            return render_template('admin/highlight_form.html', item=item)
        item.title = (request.form.get('title') or 'Match Highlight').strip()[:200]
        item.youtube_id = yt_id or ''
        item.video_url = video_url or ''
        item.description = (request.form.get('description') or '').strip()[:500]
        item.sort_order = int(request.form.get('sort_order') or 0)
        item.is_active = bool(request.form.get('is_active'))
        db.session.commit()
        flash('Highlight updated.', 'success')
        return redirect(url_for('admin.highlights'))
    return render_template('admin/highlight_form.html', item=item)


@admin_bp.route('/highlights/<int:id>/delete', methods=['POST'])
@login_required
def highlight_delete(id):
    item = Highlight.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Highlight deleted.', 'success')
    return redirect(url_for('admin.highlights'))


@admin_bp.route('/highlights/bulk-delete', methods=['POST'])
@login_required
def highlight_bulk_delete():
    ids = [int(x) for x in request.form.getlist('ids') if str(x).isdigit()]
    n = 0
    for i in ids:
        h = Highlight.query.get(i)
        if h:
            db.session.delete(h)
            n += 1
    db.session.commit()
    flash(f'Deleted {n} highlight(s).', 'success' if n else 'error')
    return redirect(url_for('admin.highlights'))
