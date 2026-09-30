"""Generate professional stadium-style digital ticket PNG (Pathari Gold Cup).

Layout: ~50% details (left) · ~50% large QR (right) for easy gate scanning.
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import qrcode

# Wide ticket — room for a large scannable QR
W, H = 1200, 520


def _open_image_any(path_or_url):
    """Open local path or https URL (Cloudinary) as RGB/RGBA PIL image."""
    if not path_or_url:
        return None
    s = str(path_or_url)
    try:
        if s.startswith('http://') or s.startswith('https://'):
            import urllib.request
            req = urllib.request.Request(s, headers={'User-Agent': 'PGC-Ticket/1.0'})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = resp.read()
            from io import BytesIO
            return Image.open(BytesIO(data))
        p = Path(s)
        if p.is_file():
            return Image.open(p)
    except Exception:
        return None
    return None



def _font(size: int, bold: bool = False):
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _load_logo(path, size=(96, 96)):
    if not path:
        return None
    try:
        img = _open_image_any(path)
        if img is None:
            return None
        img = img.convert('RGBA')
        img.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', size, (0, 0, 0, 0))
        x = (size[0] - img.width) // 2
        y = (size[1] - img.height) // 2
        canvas.paste(img, (x, y), img)
        return canvas
    except Exception:
        return None


def _placeholder_crest(draw_target, box, name, color):
    x, y, s = box
    draw_target.ellipse([x, y, x + s, y + s], fill=color, outline=(255, 215, 0), width=3)
    parts = [w for w in (name or 'FC').split() if w]
    initials = ''.join(w[0] for w in parts[:2]).upper() or 'FC'
    f = _font(max(16, s // 3), bold=True)
    bbox = draw_target.textbbox((0, 0), initials, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw_target.text((x + (s - tw) / 2, y + (s - th) / 2 - 2), initials, fill='white', font=f)


def _default_bg():
    img = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        if t < 0.52:
            r, g, b = int(8 + t * 18), int(14 + t * 28), int(32 + t * 45)
        else:
            u = (t - 0.52) / 0.48
            r, g, b = int(16 + u * 12), int(55 + u * 55), int(28 + u * 12)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    return img


def _load_background(bg_path):
    """Stadium / brand image as ticket body — keep colors visible, readable text."""
    if bg_path:
        try:
            opened = _open_image_any(bg_path)
            if opened is not None:
                bg = opened.convert('RGB')
                src_w, src_h = bg.size
                scale = max(W / src_w, H / src_h)
                nw, nh = int(src_w * scale), int(src_h * scale)
                bg = bg.resize((nw, nh), Image.Resampling.LANCZOS)
                left = (nw - W) // 2
                top = (nh - H) // 2
                bg = bg.crop((left, top, left + W, top + H))
                bg = ImageEnhance.Brightness(bg).enhance(0.82)
                bg = ImageEnhance.Contrast(bg).enhance(1.08)
                bg = ImageEnhance.Color(bg).enhance(1.1)
                overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
                od = ImageDraw.Draw(overlay)
                for y in range(H):
                    a = int(25 + (y / H) * 80)
                    od.line([(0, y), (W, y)], fill=(8, 12, 28, a))
                bg = Image.alpha_composite(bg.convert('RGBA'), overlay).convert('RGB')
                return bg
        except Exception:
            pass
    return _default_bg()


def generate_ticket_png(
    ticket,
    match,
    ticket_class,
    home_team,
    away_team,
    home_logo_path=None,
    away_logo_path=None,
    background_path=None,
    trophy_path=None,
    footer_credit='Engineered by Argon Bhujel · Pathari Gold Cup',
):
    """Half details (left) · half large QR (right)."""
    base = _load_background(background_path).convert('RGBA')
    draw = ImageDraw.Draw(base)

    GOLD = (201, 162, 39)
    GOLD_LIGHT = (255, 215, 100)
    WHITE = (255, 255, 255)
    NAVY = (10, 18, 40)
    DARK = (6, 12, 28)
    MUTED = (170, 180, 190)

    # ── Layout split: left details | right QR ─────────────────────
    # Brand strip + details ≈ left half; QR panel ≈ right half
    STRIP_W = 120
    MID = W // 2  # 600
    DETAILS_LEFT = STRIP_W + 16
    DETAILS_RIGHT = MID - 12
    QR_PANEL_X = MID + 8

    # Left brand strip
    draw.rounded_rectangle([0, 0, STRIP_W, H], radius=14, fill=DARK)

    # Trophy in strip
    if trophy_path:
        try:
            tr = _open_image_any(trophy_path)
            if tr is None:
                raise FileNotFoundError(trophy_path)
            tr = tr.convert('RGBA')
            tr.thumbnail((STRIP_W - 16, 220), Image.Resampling.LANCZOS)
            pixels = list(tr.getdata())
            cleaned = []
            for r, g, b, a in pixels:
                if r > 245 and g > 245 and b > 245:
                    cleaned.append((255, 255, 255, 0))
                else:
                    cleaned.append((r, g, b, a))
            tr.putdata(cleaned)
            tx = (STRIP_W - tr.width) // 2
            ty = 24
            base.paste(tr, (tx, ty), tr)
        except Exception:
            pass

    f_brand = _font(11, bold=True)
    for i, line in enumerate(['PATHARI', 'GOLD', 'CUP', '2026']):
        bbox = draw.textbbox((0, 0), line, font=f_brand)
        tw = bbox[2] - bbox[0]
        draw.text(((STRIP_W - tw) / 2, H - 110 + i * 18), line, fill=GOLD, font=f_brand)

    # ── LEFT HALF: match details ──────────────────────────────────
    home_full = (home_team.name if home_team else 'Home') or 'Home'
    away_full = (away_team.name if away_team else 'Away') or 'Away'
    home_short = (getattr(home_team, 'short_name', None) or home_full) if home_team else 'Home'
    away_short = (getattr(away_team, 'short_name', None) or away_full) if away_team else 'Away'

    f_title = _font(15, bold=True)
    draw.text((DETAILS_LEFT, 18), 'PATHARI GOLD CUP 2026', fill=GOLD_LIGHT, font=f_title)

    # Team crests
    s = 88
    logo_y = 52
    left_x = DETAILS_LEFT + 10
    right_x = DETAILS_LEFT + 200
    home_logo = _load_logo(home_logo_path, size=(s, s))
    away_logo = _load_logo(away_logo_path, size=(s, s))

    if home_logo:
        base.paste(home_logo, (left_x, logo_y), home_logo)
    else:
        color = (25, 55, 140)
        if home_team and getattr(home_team, 'primary_color', None):
            try:
                hex_c = home_team.primary_color.lstrip('#')
                color = tuple(int(hex_c[i:i + 2], 16) for i in (0, 2, 4))
            except Exception:
                pass
        _placeholder_crest(draw, (left_x, logo_y, s), home_full, color)

    if away_logo:
        base.paste(away_logo, (right_x, logo_y), away_logo)
    else:
        color = (140, 25, 40)
        if away_team and getattr(away_team, 'primary_color', None):
            try:
                hex_c = away_team.primary_color.lstrip('#')
                color = tuple(int(hex_c[i:i + 2], 16) for i in (0, 2, 4))
            except Exception:
                pass
        _placeholder_crest(draw, (right_x, logo_y, s), away_full, color)

    f_vs = _font(22, bold=True)
    draw.text((DETAILS_LEFT + 145, logo_y + 30), 'VS', fill=GOLD_LIGHT, font=f_vs)

    f_team = _font(12, bold=True)
    for name, cx in ((home_short.upper(), left_x + s // 2), (away_short.upper(), right_x + s // 2)):
        bbox = draw.textbbox((0, 0), name, font=f_team)
        nw = bbox[2] - bbox[0]
        draw.text((cx - nw / 2, logo_y + s + 6), name, fill=WHITE, font=f_team)

    # Date / venue
    f_meta = _font(14)
    f_meta_b = _font(15, bold=True)
    f_tiny2 = _font(11)
    meta_y = 175
    if match and match.match_date:
        dt = match.match_date
        date_str = dt.strftime('%d %b %Y').upper()
        day_str = dt.strftime('%A')
        time_str = dt.strftime('%I:%M %p')
    else:
        date_str, day_str, time_str = 'TBD', '', 'TBD'

    venue = (match.venue if match else 'Pathari, Morang') or 'Pathari, Morang'
    venue_d = (match.venue_detail if match else '') or ''

    draw.text((DETAILS_LEFT, meta_y), f'{date_str}  ·  {day_str}', fill=WHITE, font=f_meta_b)
    draw.text((DETAILS_LEFT, meta_y + 26), f'{time_str}  Kick-off', fill=WHITE, font=f_meta)
    draw.text((DETAILS_LEFT, meta_y + 52), venue, fill=WHITE, font=f_meta)
    if venue_d:
        draw.text((DETAILS_LEFT, meta_y + 74), f'({venue_d})', fill=(180, 210, 180), font=f_tiny2)

    cls_name = (ticket_class.name if ticket_class else 'General') or 'General'
    gate = (ticket_class.gate if ticket_class else 'Gate 1') or 'Gate 1'
    zone = (ticket_class.zone if ticket_class else 'East Stand') or 'East Stand'
    price = float(ticket_class.price) if ticket_class else 0
    code = ticket.ticket_code if ticket else 'PGC-TKT-XXXX'
    holder = (ticket.holder_name if ticket else '') or ''

    # Class badge + gate/zone/price
    chip_y = 290
    badge_w = max(100, 18 + len(cls_name) * 10)
    draw.rounded_rectangle([DETAILS_LEFT, chip_y, DETAILS_LEFT + badge_w, chip_y + 36], radius=8, fill=GOLD)
    f_badge = _font(14, bold=True)
    bbox = draw.textbbox((0, 0), cls_name.upper(), font=f_badge)
    bw = bbox[2] - bbox[0]
    draw.text((DETAILS_LEFT + (badge_w - bw) / 2, chip_y + 9), cls_name.upper(), fill=DARK, font=f_badge)

    col1 = DETAILS_LEFT + badge_w + 18
    draw.text((col1, chip_y + 2), 'GATE', fill=MUTED, font=f_tiny2)
    draw.text((col1, chip_y + 16), str(gate), fill=WHITE, font=f_meta_b)
    draw.text((col1 + 100, chip_y + 2), 'ZONE', fill=MUTED, font=f_tiny2)
    draw.text((col1 + 100, chip_y + 16), str(zone)[:14], fill=WHITE, font=f_meta_b)
    draw.text((col1 + 220, chip_y + 2), 'PRICE', fill=MUTED, font=f_tiny2)
    draw.text((col1 + 220, chip_y + 16), f'Rs. {price:.0f}', fill=GOLD_LIGHT, font=f_meta_b)

    if holder:
        draw.text((DETAILS_LEFT, 350), 'HOLDER', fill=MUTED, font=f_tiny2)
        draw.text((DETAILS_LEFT, 366), holder[:36], fill=WHITE, font=f_meta_b)

    draw.text((DETAILS_LEFT, 400), 'TICKET ID', fill=MUTED, font=f_tiny2)
    draw.text((DETAILS_LEFT, 416), code, fill=GOLD_LIGHT, font=f_meta_b)

    if footer_credit:
        f_cred = _font(9)
        draw.text((DETAILS_LEFT, H - 28), footer_credit[:55], fill=(140, 150, 160), font=f_cred)

    # ── RIGHT HALF: large QR panel ────────────────────────────────
    # Light panel for max QR contrast
    draw.rounded_rectangle([QR_PANEL_X, 12, W - 12, H - 12], radius=18, fill=(252, 253, 255))
    # Gold accent bar on left edge of panel
    draw.rectangle([QR_PANEL_X, 12, QR_PANEL_X + 6, H - 12], fill=GOLD)

    f_stub = _font(13, bold=True)
    f_stub_sm = _font(11)
    panel_cx = (QR_PANEL_X + W - 12) // 2

    label = 'SCAN AT GATE'
    bbox = draw.textbbox((0, 0), label, font=f_stub)
    lw = bbox[2] - bbox[0]
    draw.text((panel_cx - lw / 2, 28), label, fill=NAVY, font=f_stub)

    # Large QR — ~ half the panel, high error correction for dirty/partial scans
    payload = ticket.qr_payload if ticket and getattr(ticket, 'qr_payload', None) else code
    qr = qrcode.QRCode(
        version=None,
        box_size=12,
        border=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color='black', back_color='white').convert('RGB')

    # Target QR size: use most of right panel (~340–380px)
    QR_SIZE = 360
    qr_img = qr_img.resize((QR_SIZE, QR_SIZE), Image.Resampling.NEAREST)
    qx = panel_cx - QR_SIZE // 2
    qy = 58
    # White padding around QR
    pad = 12
    draw.rounded_rectangle(
        [qx - pad, qy - pad, qx + QR_SIZE + pad, qy + QR_SIZE + pad],
        radius=10,
        fill=(255, 255, 255),
        outline=(220, 225, 230),
        width=2,
    )
    base.paste(qr_img, (qx, qy))

    # Code under QR
    bbox = draw.textbbox((0, 0), code, font=f_stub)
    cw = bbox[2] - bbox[0]
    draw.text((panel_cx - cw / 2, qy + QR_SIZE + 18), code, fill=NAVY, font=f_stub)

    one = 'One ticket = One entry'
    bbox = draw.textbbox((0, 0), one, font=f_stub_sm)
    ow = bbox[2] - bbox[0]
    draw.text((panel_cx - ow / 2, qy + QR_SIZE + 42), one, fill=(100, 110, 120), font=f_stub_sm)

    # Outer gold border
    border = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle([2, 2, W - 3, H - 3], radius=18, outline=GOLD + (220,), width=3)
    base = Image.alpha_composite(base, border)

    out = io.BytesIO()
    base.convert('RGB').save(out, format='PNG', optimize=True)
    return out.getvalue()
