from datetime import datetime, timezone
from app.utils.timeutil import now_nepal_naive
from decimal import Decimal
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    session, send_file, current_app, abort, jsonify
)
from app.extensions import db
from app.models.match import Match
from app.models.ticket_class import TicketClass
from app.models.booking import Booking, Ticket
from app.models.settings import SiteSetting
from app.services.ticket_image import generate_ticket_png
from app.services.ticket_pdf import ticket_png_to_pdf
from app.services.uploads import save_upload
from app.services.ticket_codes import allocate_ticket_code
import io
import secrets
from pathlib import Path

public_bp = Blueprint('public', __name__)

def _ticket_assets(ticket):
    """Resolve logo/background paths or URLs for ticket PNG."""
    match = ticket.match
    tc = ticket.ticket_class
    home = match.home_team if match else None
    away = match.away_team if match else None
    from app.services.uploads import resolve_media_path
    home_logo = resolve_media_path(home.logo) if home and home.logo else None
    away_logo = resolve_media_path(away.logo) if away and away.logo else None
    bg_rel = SiteSetting.get('ticket_background', '') or 'backgrounds/ticket-bg-default.png'
    bg = resolve_media_path(bg_rel) or resolve_media_path('images/bg.png')
    qr_bg = resolve_media_path(SiteSetting.get('ticket_qr_background', '') or '')
    credit = SiteSetting.get('ticket_footer_credit', 'Engineered by Argon Bhujel · Pathari Gold Cup')
    tr = SiteSetting.get('ticket_trophy_logo', '') or 'logos/trophy-default.jpg'
    trophy = resolve_media_path(tr) or resolve_media_path('images/trophy.jpg')
    return match, tc, home, away, home_logo, away_logo, bg, credit, trophy, qr_bg


@public_bp.route('/')
def home():
    matches = []
    featured = None
    try:
        matches = Match.query.filter(Match.status.in_(['upcoming', 'live']))\
            .order_by(Match.match_date.asc()).limit(6).all()
        featured = Match.query.filter_by(is_featured=True, status='upcoming')\
            .order_by(Match.match_date.asc()).first()
        if not featured and matches:
            featured = matches[0]
    except Exception as e:
        from flask import current_app
        current_app.logger.error('home DB error: %s', e)
        # still render page shell if templates exist
        try:
            return render_template('public/home.html', matches=[], featured=None), 503
        except Exception:
            return (
                '<h1>Pathari Gold Cup</h1>'
                '<p>Database temporarily unavailable. Check DATABASE_URL / Aiven host.</p>',
                503,
            )
    return render_template('public/home.html', matches=matches, featured=featured)


@public_bp.route('/highlights')
def highlights():
    from app.models.highlight import Highlight
    items = Highlight.query.filter_by(is_active=True)\
        .order_by(Highlight.sort_order.asc(), Highlight.id.desc()).all()
    if not items:
        from app.models.settings import SiteSetting
        legacy = (SiteSetting.get('highlight_youtube') or '').strip()
        if legacy:
            items = [type('H', (), {'title': 'Match Highlight', 'youtube_id': legacy, 'description': ''})()]
    return render_template('public/highlights.html', highlights=items)


@public_bp.route('/matches')
def matches():
    items = Match.query.order_by(Match.match_date.asc()).all()
    return render_template('public/matches.html', matches=items)


@public_bp.route('/matches/<int:id>')
def match_detail(id):
    match = Match.query.get_or_404(id)
    classes = TicketClass.query.filter_by(match_id=match.id, is_active=True)\
        .order_by(TicketClass.sort_order).all()
    return render_template('public/match_detail.html', match=match, classes=classes)


@public_bp.route('/buy/<int:match_id>', methods=['GET', 'POST'])
def buy(match_id):
    match = Match.query.get_or_404(match_id)
    classes = TicketClass.query.filter_by(match_id=match.id, is_active=True)\
        .order_by(TicketClass.sort_order).all()
    if request.method == 'POST':
        class_id = request.form.get('class_id', type=int)
        qty = request.form.get('quantity', 1, type=int)
        tc = TicketClass.query.filter_by(id=class_id, match_id=match.id, is_active=True).first()
        if not tc or qty < 1 or qty > 10:
            flash('Invalid ticket selection.', 'error')
            return redirect(url_for('public.buy', match_id=match_id))
        if tc.available < qty:
            flash(f'Only {tc.available} tickets left for {tc.name}.', 'error')
            return redirect(url_for('public.buy', match_id=match_id))
        session['cart'] = {
            'match_id': match.id,
            'class_id': tc.id,
            'quantity': qty,
            'unit_price': str(tc.price),
            'class_name': tc.name,
        }
        return redirect(url_for('public.details'))
    return render_template('public/buy.html', match=match, classes=classes)


@public_bp.route('/details', methods=['GET', 'POST'])
def details():
    cart = session.get('cart')
    if not cart:
        flash('Select tickets first.', 'warning')
        return redirect(url_for('public.matches'))
    match = Match.query.get_or_404(cart['match_id'])
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        email = (request.form.get('email') or '').strip()
        if len(name) < 2 or len(phone) < 7:
            flash('Name and valid phone are required.', 'error')
            return render_template('public/details.html', match=match, cart=cart)
        if not email or '@' not in email:
            flash('Email is required — ticket ID + PNG will be sent to your email after confirmation.', 'error')
            return render_template('public/details.html', match=match, cart=cart)
        session['buyer'] = {'name': name, 'phone': phone, 'email': email}
        return redirect(url_for('public.payment'))
    return render_template('public/details.html', match=match, cart=cart)


@public_bp.route('/payment', methods=['GET', 'POST'])
def payment():
    cart = session.get('cart')
    buyer = session.get('buyer')
    if not cart or not buyer:
        return redirect(url_for('public.matches'))
    match = Match.query.get_or_404(cart['match_id'])
    tc = TicketClass.query.get_or_404(cart['class_id'])
    total = Decimal(cart['unit_price']) * int(cart['quantity'])

    esewa = SiteSetting.get('payment_esewa_enabled', 'false') == 'true'
    connectips = SiteSetting.get('payment_connectips_enabled', 'false') == 'true'
    qr_pay = SiteSetting.get('payment_qr_enabled', 'true') == 'true'

    if request.method == 'POST':
        method = request.form.get('method', 'qr')
        if method == 'esewa' and not esewa:
            flash('eSewa is currently unavailable.', 'error')
            return redirect(url_for('public.payment'))
        if method == 'connectips' and not connectips:
            flash('ConnectIPS is currently unavailable.', 'error')
            return redirect(url_for('public.payment'))

        # Payment proof upload (QR / bank transfer screenshot)
        proof_path = None
        f = request.files.get('payment_proof')
        if f and f.filename:
            proof_path = save_upload(f, folder='proofs')

        booking = Booking(
            booking_code=Booking.generate_code(),
            match_id=match.id,
            ticket_class_id=tc.id,
            quantity=int(cart['quantity']),
            unit_price=Decimal(cart['unit_price']),
            total_amount=total,
            buyer_name=buyer['name'],
            buyer_phone=buyer['phone'],
            buyer_email=buyer.get('email') or None,
            payment_method=method,
            payment_status='pending',
            payment_ref=request.form.get('txn_id') or None,
            payment_proof=proof_path,
        )

        # Instant issue only for explicit demo method (testing).
        # QR payments stay pending until admin confirms after seeing proof.
        auto_pay = method == 'demo'
        if auto_pay:
            booking.payment_status = 'paid'
            booking.paid_at = now_nepal_naive()
            if not booking.payment_ref:
                booking.payment_ref = f'DEMO-{secrets.token_hex(4).upper()}'

        db.session.add(booking)
        db.session.flush()

        tickets = []
        if booking.payment_status == 'paid':
            # sequential ticket numbers
            last = Ticket.query.order_by(Ticket.id.desc()).first()
            seq = (last.id + 1) if last else 1
            for i in range(booking.quantity):
                code = allocate_ticket_code()
                t = Ticket(
                    ticket_code=code,
                    booking_id=booking.id,
                    match_id=match.id,
                    ticket_class_id=tc.id,
                    holder_name=buyer['name'],
                    status='valid',
                    qr_payload=code,
                )
                db.session.add(t)
                tickets.append(t)
            tc.sold = (tc.sold or 0) + booking.quantity

        db.session.commit()
        session.pop('cart', None)
        session.pop('buyer', None)

        if booking.payment_status == 'paid':
            try:
                from app.services.notify import notify_tickets_issued
                issued = Ticket.query.filter_by(booking_id=booking.id).all()
                if issued:
                    notify_tickets_issued(booking, issued)
            except Exception as e:
                current_app.logger.warning('Instant ticket notify: %s', e)
            return redirect(url_for('public.success', code=booking.booking_code))

        mail_ok = False
        try:
            from app.services.notify import send_booking_received_email
            mail_ok = bool(send_booking_received_email(booking))
        except Exception as e:
            current_app.logger.warning('Booking received mail: %s', e)
        if mail_ok:
            flash('Your booking has been received. Confirmation email sent.', 'success')
        else:
            flash(
                'Your booking has been received. '
                'Email could not be sent - keep your booking code safe.',
                'info',
            )
        return redirect(url_for('public.success', code=booking.booking_code))

    qr_image = SiteSetting.get('payment_qr_image', '')
    instructions = SiteSetting.get('payment_instructions', '')
    return render_template(
        'public/payment.html',
        match=match, cart=cart, buyer=buyer, total=total, tc=tc,
        esewa=esewa, connectips=connectips, qr_pay=qr_pay,
        qr_image=qr_image, instructions=instructions,
    )


@public_bp.route('/success/<code>')
def success(code):
    booking = Booking.query.filter_by(booking_code=code).first_or_404()
    tickets = Ticket.query.filter_by(booking_id=booking.id).all()
    return render_template('public/success.html', booking=booking, tickets=tickets)


@public_bp.route('/ticket/<code>')
def ticket_view(code):
    ticket = Ticket.query.filter_by(ticket_code=code).first_or_404()
    return render_template('public/ticket.html', ticket=ticket)


@public_bp.route('/ticket/<code>/png')
def ticket_png(code):
    ticket = Ticket.query.filter_by(ticket_code=code).first_or_404()
    match, tc, home, away, home_logo, away_logo, bg, credit, trophy, qr_bg = _ticket_assets(ticket)
    png = generate_ticket_png(ticket, match, tc, home, away, home_logo, away_logo,
                             background_path=bg, trophy_path=trophy, footer_credit=credit,
                             qr_background_path=qr_bg)
    return send_file(io.BytesIO(png), mimetype='image/png',
                     download_name=f'{ticket.ticket_code}.png', as_attachment=True)


@public_bp.route('/ticket/<code>/preview.png')
def ticket_preview(code):
    """Inline PNG for display (not attachment)."""
    ticket = Ticket.query.filter_by(ticket_code=code).first_or_404()
    match, tc, home, away, home_logo, away_logo, bg, credit, trophy, qr_bg = _ticket_assets(ticket)
    png = generate_ticket_png(ticket, match, tc, home, away, home_logo, away_logo,
                             background_path=bg, trophy_path=trophy, footer_credit=credit,
                             qr_background_path=qr_bg)
    return send_file(io.BytesIO(png), mimetype='image/png')


@public_bp.route('/ticket/<code>/pdf')
def ticket_pdf(code):
    ticket = Ticket.query.filter_by(ticket_code=code).first_or_404()
    match, tc, home, away, home_logo, away_logo, bg, credit, trophy, qr_bg = _ticket_assets(ticket)
    png = generate_ticket_png(ticket, match, tc, home, away, home_logo, away_logo,
                             background_path=bg, trophy_path=trophy, footer_credit=credit,
                             qr_background_path=qr_bg)
    pdf = ticket_png_to_pdf(png, ticket.ticket_code)
    return send_file(io.BytesIO(pdf), mimetype='application/pdf',
                     download_name=f'{ticket.ticket_code}.pdf', as_attachment=True)


@public_bp.route('/verify', methods=['GET', 'POST'])
def verify():
    result = None
    code = ''
    if request.method == 'POST':
        code = (request.form.get('code') or '').strip().upper()
        ticket = Ticket.query.filter_by(ticket_code=code).first()
        if ticket:
            result = ticket
        else:
            flash('Ticket not found.', 'error')
    elif request.args.get('code'):
        code = request.args.get('code').strip().upper()
        result = Ticket.query.filter_by(ticket_code=code).first()
    return render_template('public/verify.html', ticket=result, code=code)




@public_bp.route('/sw.js')
def service_worker():
    """Service worker at root so scope covers whole site."""
    from flask import current_app, make_response, send_from_directory
    resp = make_response(send_from_directory(current_app.static_folder, 'sw.js'))
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@public_bp.route('/manifest.webmanifest')
def web_manifest():
    from flask import current_app, send_from_directory
    return send_from_directory(current_app.static_folder, 'manifest.webmanifest',
                               mimetype='application/manifest+json')

@public_bp.route('/about')
def about():
    return render_template('public/about.html')


@public_bp.route('/media/<path:filename>')
def media(filename):
    """Serve local upload or redirect Cloudinary / absolute URLs."""
    from flask import send_from_directory, redirect
    # full URL stored as path somehow
    if filename.startswith('http://') or filename.startswith('https://'):
        return redirect(filename)
    # Cloudinary path accidentally stored without scheme handled above
    if 'res.cloudinary.com' in filename:
        return redirect('https://' + filename.lstrip('/'))
    root = Path(current_app.config['UPLOAD_FOLDER'])
    return send_from_directory(root, filename)




@public_bp.route('/booking-status', methods=['GET', 'POST'])
def booking_status():
    from app.models.booking import Booking, Ticket
    booking = None
    tickets = []
    searched = False
    booking_code = ''
    email = ''
    if request.method == 'POST':
        searched = True
        booking_code = (request.form.get('booking_code') or '').strip().upper()
        email = (request.form.get('email') or '').strip().lower()
        if booking_code and email:
            booking = Booking.query.filter(
                Booking.booking_code == booking_code
            ).first()
            if booking and (booking.buyer_email or '').strip().lower() != email:
                booking = None
            if booking:
                tickets = Ticket.query.filter_by(booking_id=booking.id).all()
    return render_template(
        'public/booking_status.html',
        booking=booking, tickets=tickets, searched=searched,
        booking_code=booking_code, email=email,
    )

@public_bp.route('/robots.txt')
def robots_txt():
    sitemap = request.url_root.rstrip('/') + '/sitemap.xml'
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /admin',
        'Disallow: /gate',
        'Disallow: /scanner',
        'Disallow: /success',
        f'Sitemap: {sitemap}',
        '',
    ]
    return current_app.response_class('\n'.join(lines), mimetype='text/plain')


@public_bp.route('/sitemap.xml')
def sitemap_xml():
    from app.models.match import Match
    base = request.url_root.rstrip('/')
    urls = [
        ('/', '1.0', 'daily'),
        ('/matches', '0.9', 'daily'),
        ('/about', '0.7', 'weekly'),
        ('/verify', '0.5', 'monthly'),
    ]
    for m in Match.query.filter_by(status='upcoming').order_by(Match.match_date).limit(50).all():
        urls.append((f'/buy/{m.id}', '0.8', 'daily'))
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, pri, freq in urls:
        parts.append(
            f'<url><loc>{base}{path}</loc>'
            f'<changefreq>{freq}</changefreq><priority>{pri}</priority></url>'
        )
    parts.append('</urlset>')
    return current_app.response_class('\n'.join(parts), mimetype='application/xml')
