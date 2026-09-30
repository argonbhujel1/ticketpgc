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

    subject = f'Your Ticket — Pathari Sanischare Gold Cup ({booking.booking_code})'

    text_body = f"""PATHARI SANISCHARE GOLD CUP
Official Ticketing System

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

    html_body = f"""
<!DOCTYPE html>
<html><body style="font-family:Arial,Helvetica,sans-serif;color:#111;line-height:1.5;
  max-width:640px;margin:0 auto;padding:16px;background:#0a0a0c">
  <div style="background:#141018;border-radius:16px;padding:20px;border:1px solid #c9a227">
    <div style="text-align:center;border-bottom:2px solid #c9a227;padding-bottom:12px;margin-bottom:16px">
      <div style="font-size:18px;font-weight:bold;color:#c9a227;letter-spacing:0.04em">
        PATHARI SANISCHARE GOLD CUP
      </div>
      <div style="font-size:13px;color:#aaa">Official Ticketing System</div>
    </div>

    <p style="color:#f0f0f0">Hello <b style="color:#ffd54f">{booking.buyer_name}</b>,</p>
    <p style="color:#ccc">Your ticket has been successfully created.</p>

    <div style="background:#1a1218;border:1px solid #c9a22755;border-radius:8px;padding:16px;margin:16px 0">
      <div style="font-size:12px;color:#c9a227;font-weight:bold;letter-spacing:0.08em;margin-bottom:10px">
        TICKET DETAILS
      </div>
      <table style="width:100%;font-size:14px;border-collapse:collapse;color:#eee">
        <tr><td style="padding:4px 0;color:#888;width:38%">Ticket ID</td>
            <td style="padding:4px 0"><b>{ticket_id_line}</b></td></tr>
        <tr><td style="padding:4px 0;color:#888">Name</td>
            <td style="padding:4px 0">{booking.buyer_name}</td></tr>
        <tr><td style="padding:4px 0;color:#888">Mobile</td>
            <td style="padding:4px 0">{booking.buyer_phone or '—'}</td></tr>
        <tr><td style="padding:4px 0;color:#888">Ticket Type</td>
            <td style="padding:4px 0">{ticket_type}</td></tr>
        <tr><td style="padding:4px 0;color:#888">Quantity</td>
            <td style="padding:4px 0">{qty}</td></tr>
        <tr><td style="padding:4px 0;color:#888">Amount</td>
            <td style="padding:4px 0"><b>NPR {amount:.0f}</b></td></tr>
        <tr><td style="padding:4px 0;color:#888">Status</td>
            <td style="padding:4px 0;color:#81c784"><b>Confirmed</b></td></tr>
      </table>
    </div>

    <p style="color:#c9a227;font-weight:bold;text-align:center;margin:20px 0 8px">YOUR OFFICIAL TICKET</p>
    {tickets_html}

    <p style="color:#aaa;font-size:13px;margin-top:20px">
      Present the QR at the gate. One ticket = one entry.<br>
      <b style="color:#e57373">This is an automated message — please do not reply.</b>
    </p>

    <p style="margin-top:24px;color:#eee">Regards,<br>
      <b style="color:#c9a227">Pathari Sanischare Gold Cup</b><br>
      <span style="color:#888;font-size:13px">Official Ticketing System</span>
    </p>
  </div>
</body></html>
"""

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
    cfg = _mail_cfg()
    if not cfg.get('username') or not cfg.get('password') or not cfg.get('sender'):
        return False
    reason = (booking.rejection_reason or 'No reason provided.').strip()
    subject = f'Booking {booking.booking_code} — Not approved'
    body = (
        f'Dear {booking.buyer_name},' + chr(10) + chr(10)
        + f'Your booking {booking.booking_code} was not approved.' + chr(10) + chr(10)
        + f'Reason: {reason}' + chr(10) + chr(10)
        + 'If you have questions, contact the organizers.' + chr(10) + chr(10)
        + '— Pathari Gold Cup' + chr(10)
    )
    try:
        from email.mime.text import MIMEText
        import smtplib
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = cfg['sender']
        msg['To'] = to
        with smtplib.SMTP(cfg['server'], cfg['port'], timeout=12) as s:
            if cfg['use_tls']:
                s.starttls()
            s.login(cfg['username'], cfg['password'])
            s.sendmail(cfg['sender'], [to], msg.as_string())
        return True
    except Exception as e:
        current_app.logger.warning('reject email failed: %s', e)
        return False
