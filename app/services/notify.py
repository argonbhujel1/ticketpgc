"""Ticket delivery via professional email — full ticket embedded (not plain photo dump)."""
from __future__ import annotations

import os
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

from flask import current_app

# Official from-address (display + envelope)
OFFICIAL_FROM_EMAIL = os.environ.get(
    'MAIL_DEFAULT_SENDER',
    os.environ.get('MAIL_USERNAME', 'pathrisanischaregoldcup@gmail.com'),
)
OFFICIAL_FROM_NAME = 'Pathari Sanischare Gold Cup'
NOREPLY_HINT = 'pathrisanischaregoldcup@gmail.com'


def _mail_cfg():
    sender = os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get(
        'MAIL_USERNAME', 'pathrisanischaregoldcup@gmail.com'
    )
    return {
        'server': os.environ.get('MAIL_SERVER', ''),
        'port': int(os.environ.get('MAIL_PORT', 587)),
        'use_tls': os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes'),
        'username': os.environ.get('MAIL_USERNAME', ''),
        'password': os.environ.get('MAIL_PASSWORD', ''),
        'sender': sender,
    }



def _load_logo_bytes():
    try:
        from app.models.settings import SiteSetting
        from app.services.uploads import resolve_media_path
        rel = SiteSetting.get('site_logo', '') or ''
        path = resolve_media_path(rel) if rel else None
        if not path:
            static = Path(current_app.static_folder)
            for name in ('images/logo.jpg', 'images/logo.png', 'images/icon-180.png'):
                cand = static / name
                if cand.is_file():
                    path = str(cand)
                    break
        if not path:
            return None
        if str(path).startswith('http'):
            import urllib.request
            req = urllib.request.Request(path, headers={'User-Agent': 'PGC-Mail/1.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read(), 'png' if 'png' in path.lower() else 'jpeg'
        data = Path(path).read_bytes()
        ext = 'png' if path.lower().endswith('.png') else 'jpeg'
        return data, ext
    except Exception as e:
        current_app.logger.debug('logo load: %s', e)
        return None


def _nepal_stamp():
    from app.utils.timeutil import format_nepal, now_nepal
    return format_nepal(now_nepal(), '%d %b %Y | %I:%M:%S %p NPT')


def _email_shell(title, inner_html, badge_text='OFFICIAL'):
    stamp = _nepal_stamp()
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#070b14;font-family:Arial,Helvetica,sans-serif;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#070b14;padding:24px 12px;">'
        '<tr><td align="center">'
        '<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%;background:#0d1526;border-radius:16px;border:1px solid #c9a227;overflow:hidden;">'
        '<tr><td style="background:#1a1408;padding:20px 24px;text-align:center;border-bottom:2px solid #c9a227;">'
        '<img src="cid:site-logo" alt="Logo" width="72" height="72" '
        'style="width:72px;height:72px;border-radius:50%;object-fit:cover;border:2px solid #c9a227;background:#fff;">'
        '<div style="margin-top:10px;color:#ffd56a;font-size:18px;font-weight:bold;">Pathari Sanischare Gold Cup</div>'
        '<div style="color:#8b93a7;font-size:12px;margin-top:4px;">Official Ticketing System</div>'
        '</td></tr>'
        '<tr><td style="padding:12px 24px;background:#121a2a;">'
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        f'<td><span style="display:inline-block;padding:4px 12px;border:1px solid #c9a227;border-radius:999px;color:#ffd56a;font-size:11px;font-weight:bold;letter-spacing:0.06em;">{badge_text}</span></td>'
        f'<td align="right" style="color:#8b93a7;font-size:11px;">{stamp}</td>'
        '</tr></table></td></tr>'
        '<tr><td style="padding:24px;color:#f0f2f5;font-size:15px;line-height:1.55;">'
        f'<h1 style="margin:0 0 16px;color:#ffd56a;font-size:20px;">{title}</h1>'
        f'{inner_html}'
        '</td></tr>'
        '<tr><td style="padding:16px 24px 24px;border-top:1px solid #243044;text-align:center;">'
        '<p style="margin:0 0 8px;color:#8b93a7;font-size:12px;line-height:1.5;">'
        'This is an <strong style="color:#c9a227;">auto-generated</strong> email from Pathari Sanischare Gold Cup.<br>'
        'Please <strong>do not reply</strong> to this message.</p>'
        '<p style="margin:0;color:#555;font-size:11px;">&copy; Pathari Sanischare Gold Cup</p>'
        '</td></tr></table></td></tr></table></body></html>'
    )


def _attach_logo(related_part):
    logo = _load_logo_bytes()
    if not logo:
        return
    data, ext = logo
    img = MIMEImage(data, _subtype='png' if ext == 'png' else 'jpeg')
    img.add_header('Content-ID', '<site-logo>')
    img.add_header('Content-Disposition', 'inline', filename='logo.' + ('png' if ext == 'png' else 'jpg'))
    related_part.attach(img)


def _send_html_mail(to, subject, text_body, html_body, extra_related_attachments=None, file_attachments=None):
    cfg = _mail_cfg()
    if not cfg.get('server') or not cfg.get('sender'):
        return False
    if not cfg.get('username') or not cfg.get('password'):
        current_app.logger.warning('MAIL credentials missing')
        return False
    msg = MIMEMultipart('mixed')
    msg['Subject'] = subject
    msg['From'] = formataddr((OFFICIAL_FROM_NAME, cfg['sender']))
    msg['To'] = to
    msg['X-Auto-Response-Suppress'] = 'All'
    msg['Auto-Submitted'] = 'auto-generated'
    msg['Precedence'] = 'bulk'
    related = MIMEMultipart('related')
    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(text_body, 'plain', 'utf-8'))
    alt.attach(MIMEText(html_body, 'html', 'utf-8'))
    related.attach(alt)
    _attach_logo(related)
    if extra_related_attachments:
        for item in extra_related_attachments:
            related.attach(item)
    msg.attach(related)
    if file_attachments:
        for att in file_attachments:
            msg.attach(att)
    try:
        with smtplib.SMTP(cfg['server'], cfg['port'], timeout=20) as s:
            if cfg.get('use_tls'):
                s.starttls()
            s.login(cfg['username'], cfg['password'])
            s.sendmail(cfg['sender'], [to], msg.as_string())
        return True
    except Exception as e:
        current_app.logger.warning('Email send failed: %s', e)
        return False

def _build_ticket_pngs(tickets):
    from app.services.ticket_image import generate_ticket_png
    from app.models.settings import SiteSetting
    from app.services.uploads import resolve_media_path

    bg_rel = SiteSetting.get('ticket_background', '') or 'backgrounds/ticket-bg-default.png'
    bg = resolve_media_path(bg_rel) or resolve_media_path('images/bg.png')
    qr_bg = resolve_media_path(SiteSetting.get('ticket_qr_background', '') or '')
    tr = SiteSetting.get('ticket_trophy_logo', '') or 'logos/trophy-default.jpg'
    trophy = resolve_media_path(tr) or resolve_media_path('images/trophy.jpg')
    credit = SiteSetting.get(
        'ticket_footer_credit',
        'Engineered by Argon Bhujel · Pathari Sanischare Gold Cup',
    )

    out = []
    for t in tickets:
        match = t.match
        tc = t.ticket_class
        home = match.home_team if match else None
        away = match.away_team if match else None
        home_logo = resolve_media_path(home.logo) if home and home.logo else None
        away_logo = resolve_media_path(away.logo) if away and away.logo else None
        png = generate_ticket_png(
            t, match, tc, home, away, home_logo, away_logo,
            background_path=bg, trophy_path=trophy, footer_credit=credit,
            qr_background_path=qr_bg,
        )
        out.append((t.ticket_code, png))
    return out


def _ticket_type_name(tickets):
    if not tickets:
        return '—'
    seen = []
    for t in tickets:
        n = t.ticket_class.name if t.ticket_class else None
        if n and n not in seen:
            seen.append(n)
    return ', '.join(seen) if seen else '—'


def send_ticket_email(booking, tickets):
    """
    Email contains the real digital ticket(s) embedded inline (CID).
    From: Pathari Sanischare Gold Cup <pathrisanischaregoldcup@gmail.com>
    No Reply-To — replies discouraged.
    """
    to = (booking.buyer_email or '').strip()
    if not to:
        current_app.logger.warning(
            'No buyer email on booking %s', booking.booking_code,
        )
        return False

    cfg = _mail_cfg()
    if not cfg['server'] or not cfg['sender']:
        current_app.logger.warning('MAIL not configured')
        return False

    site_url = os.environ.get('SITE_URL', '').rstrip('/')
    qty = len(tickets) if tickets else int(booking.quantity or 1)
    amount = float(booking.total_amount or 0)
    ticket_type = _ticket_type_name(tickets)
    codes = [t.ticket_code for t in tickets] if tickets else []
    ticket_id_line = ', '.join(codes) if codes else booking.booking_code

    stamp = _nepal_stamp()
    subject = f'Your Ticket — Pathari Sanischare Gold Cup ({booking.booking_code})'

    text_body = f"""PATHARI SANISCHARE GOLD CUP
Official Ticketing System
Time: {stamp}

Hello {booking.buyer_name},

Your ticket has been successfully created.

━━━━━━━━━━━━━━━━━━━━
TICKET DETAILS
━━━━━━━━━━━━━━━━━━━━
Ticket ID       : {ticket_id_line}
Name            : {booking.buyer_name}
Mobile          : {booking.buyer_phone or '—'}
Ticket Type     : {ticket_type}
Quantity        : {qty}
Amount          : NPR {amount:.0f}
Status          : Confirmed
Booking         : {booking.booking_code}
━━━━━━━━━━━━━━━━━━━━

Your official digital ticket image is included in this email.
Present the QR code at the gate. Single use only.

This is an automated message — please do not reply to this email.

Regards,
Pathari Sanischare Gold Cup
Official Ticketing System
"""

    # HTML: embed each ticket as full-width ticket card (cid:ticket-N)
    ticket_blocks = []
    for i, code in enumerate(codes):
        ticket_blocks.append(f'''
        <div style="margin:20px 0;text-align:center">
          <p style="font-size:12px;color:#888;margin-bottom:8px">Ticket {i + 1} · <b style="color:#111">{code}</b></p>
          <img src="cid:ticket-{i}" alt="Ticket {code}"
               width="600" style="max-width:100%;height:auto;border-radius:12px;
               border:2px solid #c9a227;display:block;margin:0 auto">
        </div>
        ''')
    tickets_html = '\n'.join(ticket_blocks) if ticket_blocks else '<p>Ticket details above.</p>'

    inner = f"""
    <p style="margin:0 0 12px">Hello <strong>{booking.buyer_name}</strong>,</p>
    <p style="margin:0 0 16px">Your ticket has been
      <strong style="color:#81c784">successfully issued</strong>.</p>
    <table width="100%" cellspacing="0" cellpadding="0" style="background:#121a2a;border-radius:12px;border:1px solid #243044;margin-bottom:18px">
      <tr><td style="padding:12px 16px;color:#8b93a7;font-size:13px">Ticket ID</td>
          <td style="padding:12px 16px;color:#ffd56a;font-weight:bold">{ticket_id_line}</td></tr>
      <tr><td style="padding:10px 16px;color:#8b93a7;font-size:13px;border-top:1px solid #243044">Name</td>
          <td style="padding:10px 16px;border-top:1px solid #243044">{booking.buyer_name}</td></tr>
      <tr><td style="padding:10px 16px;color:#8b93a7;font-size:13px;border-top:1px solid #243044">Mobile</td>
          <td style="padding:10px 16px;border-top:1px solid #243044">{booking.buyer_phone or '-'}</td></tr>
      <tr><td style="padding:10px 16px;color:#8b93a7;font-size:13px;border-top:1px solid #243044">Type</td>
          <td style="padding:10px 16px;border-top:1px solid #243044">{ticket_type}</td></tr>
      <tr><td style="padding:10px 16px;color:#8b93a7;font-size:13px;border-top:1px solid #243044">Qty / Amount</td>
          <td style="padding:10px 16px;border-top:1px solid #243044">{qty} | NPR {amount:.0f}</td></tr>
      <tr><td style="padding:10px 16px;color:#8b93a7;font-size:13px;border-top:1px solid #243044">Booking</td>
          <td style="padding:10px 16px;border-top:1px solid #243044">{booking.booking_code}</td></tr>
    </table>
    {tickets_html}
    <p style="margin:16px 0 0;color:#8b93a7;font-size:13px">
      Present the QR at the gate. Single use only.
    </p>
    """
    html_body = _email_shell('Your official ticket', inner, badge_text='TICKET ISSUED')


    # related: HTML + inline ticket images (looks like real ticket in mail client)
    msg_root = MIMEMultipart('mixed')
    msg_root['Subject'] = subject
    msg_root['From'] = formataddr((OFFICIAL_FROM_NAME, cfg['sender']))
    msg_root['To'] = to
    # No Reply-To header → clients reply to From; we discourage replies in body.
    # Explicitly mark as auto-generated / no replies.
    msg_root['X-Auto-Response-Suppress'] = 'All'
    msg_root['Auto-Submitted'] = 'auto-generated'
    msg_root['Precedence'] = 'bulk'

    msg_related = MIMEMultipart('related')
    msg_alt = MIMEMultipart('alternative')
    msg_alt.attach(MIMEText(text_body, 'plain', 'utf-8'))
    msg_alt.attach(MIMEText(html_body, 'html', 'utf-8'))
    msg_related.attach(msg_alt)

    pngs = []
    try:
        pngs = _build_ticket_pngs(tickets)
    except Exception as e:
        current_app.logger.warning('Ticket PNG build failed: %s', e)

    for i, (code, png) in enumerate(pngs):
        # Inline (CID) — shows as the ticket inside the email
        img = MIMEImage(png, _subtype='png')
        img.add_header('Content-ID', f'<ticket-{i}>')
        img.add_header('Content-Disposition', 'inline', filename=f'{code}.png')
        msg_related.attach(img)
        # Also attach so user can save the file
        att = MIMEImage(png, _subtype='png')
        att.add_header('Content-Disposition', 'attachment', filename=f'{code}.png')
        msg_root.attach(att)

    msg_root.attach(msg_related)

    # If we attached twice structure is wrong - fix order:
    # Standard: mixed contains [related (alt+inline images)] + optional attachments
    # Rebuild cleanly:
    msg = MIMEMultipart('mixed')
    msg['Subject'] = subject
    msg['From'] = formataddr((OFFICIAL_FROM_NAME, cfg['sender']))
    msg['To'] = to
    msg['X-Auto-Response-Suppress'] = 'All'
    msg['Auto-Submitted'] = 'auto-generated'
    msg['Precedence'] = 'bulk'

    related = MIMEMultipart('related')
    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(text_body, 'plain', 'utf-8'))
    alt.attach(MIMEText(html_body, 'html', 'utf-8'))
    related.attach(alt)
    for i, (code, png) in enumerate(pngs):
        img = MIMEImage(png, _subtype='png')
        img.add_header('Content-ID', f'<ticket-{i}>')
        img.add_header('Content-Disposition', 'inline', filename=f'{code}.png')
        related.attach(img)
    msg.attach(related)
    # downloadable copies
    for code, png in pngs:
        att = MIMEImage(png, _subtype='png')
        att.add_header('Content-Disposition', 'attachment', filename=f'{code}.png')
        msg.attach(att)

    try:
        with smtplib.SMTP(cfg['server'], cfg['port'], timeout=15) as s:
            if cfg['use_tls']:
                s.starttls()
            if cfg['username'] and cfg['password']:
                s.login(cfg['username'], cfg['password'])
            s.sendmail(cfg['sender'], [to], msg.as_string())
        current_app.logger.info('Ticket email sent to %s from %s', to, cfg['sender'])
        return True
    except Exception as e:
        current_app.logger.warning('Email failed: %s', e)
        return False


def notify_tickets_issued(booking, tickets):
    email_ok = False
    email_detail = ''
    try:
        email_ok = send_ticket_email(booking, tickets)
        if not email_ok:
            email_detail = 'failed (buyer email + MAIL_* required)'
    except Exception as e:
        current_app.logger.warning('Email error: %s', e)
        email_detail = str(e)
    return {'sms': False, 'email': email_ok, 'sms_error': 'disabled', 'email_error': email_detail}


def send_ticket_invalidated_email(ticket_code, holder_name, to_email, reason='removed by admin'):
    """Notify owner that their ticket is no longer valid."""
    if not to_email:
        current_app.logger.info('No email for invalidated ticket %s', ticket_code)
        return False
    cfg = _mail_cfg()
    if not cfg['server'] or not cfg['sender']:
        current_app.logger.warning('MAIL not configured — skip invalidation email')
        return False

    subject = f'Ticket {ticket_code} is no longer valid — Pathari Sanischare Gold Cup'
    text = f"""PATHARI SANISCHARE GOLD CUP
Official Ticketing System

Hello {holder_name or 'Customer'},

Your ticket was invalid and removed.

Ticket ID : {ticket_code}
Status    : Invalid / Removed
Reason    : {reason}

This ticket number can no longer be used for entry at the gate.
If you believe this was a mistake, please contact the organizers through official channels (do not reply to this email).

Regards,
Pathari Sanischare Gold Cup
Official Ticketing System
"""
    html = f"""
<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:16px;background:#0a0a0c;color:#eee">
  <div style="border:1px solid #c62828;border-radius:12px;padding:20px;background:#141018">
    <div style="color:#c9a227;font-weight:bold;margin-bottom:12px">PATHARI SANISCHARE GOLD CUP</div>
    <p>Hello <b>{holder_name or 'Customer'}</b>,</p>
    <p style="color:#e57373;font-weight:bold">Your ticket was invalid and removed.</p>
    <table style="width:100%;font-size:14px">
      <tr><td style="color:#888">Ticket ID</td><td><b>{ticket_code}</b></td></tr>
      <tr><td style="color:#888">Status</td><td style="color:#e57373">Invalid / Removed</td></tr>
    </table>
    <p style="color:#aaa;font-size:13px;margin-top:16px">This ticket cannot be used at the gate.<br>
    This is an automated message — please do not reply.</p>
    <p>Regards,<br><b style="color:#c9a227">Pathari Sanischare Gold Cup</b></p>
  </div>
</body></html>
"""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = formataddr((OFFICIAL_FROM_NAME, cfg['sender']))
    msg['To'] = to_email
    msg['X-Auto-Response-Suppress'] = 'All'
    msg['Auto-Submitted'] = 'auto-generated'
    msg.attach(MIMEText(text, 'plain', 'utf-8'))
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    try:
        with smtplib.SMTP(cfg['server'], cfg['port'], timeout=12) as s:
            if cfg['use_tls']:
                s.starttls()
            if cfg['username'] and cfg['password']:
                s.login(cfg['username'], cfg['password'])
            s.sendmail(cfg['sender'], [to_email], msg.as_string())
        current_app.logger.info('Invalidation email sent for %s to %s', ticket_code, to_email)
        return True
    except Exception as e:
        current_app.logger.warning('Invalidation email failed: %s', e)
        return False



def send_booking_rejected_email(booking):
    """Notify buyer that booking was rejected with reason."""
    to = (booking.buyer_email or '').strip()
    if not to:
        return False
    reason = (booking.rejection_reason or 'No reason provided.').strip()
    name = booking.buyer_name or 'Guest'
    code = booking.booking_code
    stamp = _nepal_stamp()
    subject = f'Booking {code} - Not approved'
    nl = chr(10)
    text_body = (
        f'Dear {name},' + nl + nl
        + f'Your booking {code} was not approved.' + nl + nl
        + f'Reason: {reason}' + nl + nl
        + f'Time: {stamp}' + nl + nl
        + 'This is an auto-generated email. Please do not reply.' + nl
    )
    inner = (
        f'<p>Dear <strong>{name}</strong>,</p>'
        f'<p>Your booking <strong style="color:#ffd56a">{code}</strong> was '
        f'<strong style="color:#ef9a9a">not approved</strong>.</p>'
        f'<div style="margin:16px 0;padding:14px 16px;background:#2a1212;border-radius:12px;border:1px solid #e53935;">'
        f'<div style="color:#8b93a7;font-size:12px;margin-bottom:6px">Reason</div>'
        f'<div style="color:#f0f2f5">{reason}</div></div>'
        f'<p style="color:#8b93a7;font-size:13px">Contact organizers through official channels if needed.</p>'
    )
    html_body = _email_shell('Booking not approved', inner, badge_text='REJECTED')
    return _send_html_mail(to, subject, text_body, html_body)


def send_booking_received_email(booking):
    """Email buyer immediately after they submit a booking (pending approval)."""
    to = (booking.buyer_email or '').strip()
    if not to:
        current_app.logger.warning('No email for booking received: %s', booking.booking_code)
        return False

    match_name = booking.match.display_name if booking.match else 'Match'
    class_name = booking.ticket_class.name if booking.ticket_class else 'Ticket'
    qty = int(booking.quantity or 1)
    amount = float(booking.total_amount or 0)
    code = booking.booking_code
    name = booking.buyer_name or 'Guest'
    stamp = _nepal_stamp()

    subject = f'Booking received - {code}'
    nl = chr(10)
    text_body = (
        'PATHARI SANISCHARE GOLD CUP' + nl
        + f'Time: {stamp}' + nl + nl
        + f'Dear {name},' + nl + nl
        + 'Your booking has been received.' + nl + nl
        + f'Booking code: {code}' + nl
        + f'Match: {match_name}' + nl
        + f'Ticket: {class_name} x {qty}' + nl
        + f'Amount: Rs. {amount:.0f}' + nl
        + 'Status: Pending admin approval' + nl + nl
        + 'We will email your digital ticket after payment is confirmed.' + nl + nl
        + 'This is an auto-generated email. Please do not reply.' + nl + nl
        + '- Pathari Sanischare Gold Cup' + nl
    )

    inner = (
        f'<p style="margin:0 0 14px">Dear <strong>{name}</strong>,</p>'
        f'<p style="margin:0 0 18px">Your booking has been '
        f'<strong style="color:#81c784">received</strong> successfully.</p>'
        f'<table width="100%" cellspacing="0" cellpadding="0" style="background:#121a2a;border-radius:12px;border:1px solid #243044;">'
        f'<tr><td style="padding:14px 16px;color:#8b93a7;font-size:13px">Booking code</td>'
        f'<td style="padding:14px 16px;color:#ffd56a;font-weight:bold;font-size:15px">{code}</td></tr>'
        f'<tr><td style="padding:10px 16px;color:#8b93a7;font-size:13px;border-top:1px solid #243044">Match</td>'
        f'<td style="padding:10px 16px;border-top:1px solid #243044">{match_name}</td></tr>'
        f'<tr><td style="padding:10px 16px;color:#8b93a7;font-size:13px;border-top:1px solid #243044">Ticket</td>'
        f'<td style="padding:10px 16px;border-top:1px solid #243044">{class_name} x {qty}</td></tr>'
        f'<tr><td style="padding:10px 16px;color:#8b93a7;font-size:13px;border-top:1px solid #243044">Amount</td>'
        f'<td style="padding:10px 16px;border-top:1px solid #243044">Rs. {amount:.0f}</td></tr>'
        f'<tr><td style="padding:10px 16px;color:#8b93a7;font-size:13px;border-top:1px solid #243044">Status</td>'
        f'<td style="padding:10px 16px;border-top:1px solid #243044;color:#ffcc80">Pending approval</td></tr>'
        f'</table>'
        f'<p style="margin:18px 0 0;color:#8b93a7;font-size:13px">'
        f'After admin confirms payment, you will receive another email with your digital ticket and QR code.</p>'
    )
    html_body = _email_shell('Booking received', inner, badge_text='BOOKING RECEIVED')
    ok = _send_html_mail(to, subject, text_body, html_body)
    if ok:
        current_app.logger.info('Booking received email sent to %s for %s', to, code)
    return ok
