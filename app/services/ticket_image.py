"""Generate professional stadium-style digital ticket PNG (Pathari Gold Cup)."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import qrcode

W, H = 1200, 420


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
    p = Path(path)
    if not p.is_file():
        return None
    try:
        img = Image.open(p).convert('RGBA')
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
    f = _font(22, bold=True)
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
    if bg_path and Path(bg_path).is_file():
        try:
            bg = Image.open(bg_path).convert('RGB')
            # Cover-fit: fill canvas, crop center
            src_w, src_h = bg.size
            scale = max(W / src_w, H / src_h)
            nw, nh = int(src_w * scale), int(src_h * scale)
            bg = bg.resize((nw, nh), Image.Resampling.LANCZOS)
            left = (nw - W) // 2
            top = (nh - H) // 2
            bg = bg.crop((left, top, left + W, top + H))
            # Gentle darken only (not muddy)
            bg = ImageEnhance.Brightness(bg).enhance(0.85)
            bg = ImageEnhance.Contrast(bg).enhance(1.08)
            bg = ImageEnhance.Color(bg).enhance(1.1)
            # Soft gradient scrim: darker bottom for meta text, lighter top for logos
            overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            for y in range(H):
                # top light, bottom stronger for readability
                a = int(20 + (y / H) * 70)
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
    base = _load_background(background_path).convert('RGBA')
    draw = ImageDraw.Draw(base)

    GOLD = (201, 162, 39)
    GOLD_LIGHT = (255, 215, 100)
    WHITE = (255, 255, 255)
    NAVY = (10, 18, 40)
    DARK = (6, 12, 28)

    # Left strip — full trophy photo (t.jpg), brand text below
    STRIP_W = 160
    draw.rounded_rectangle([0, 0, STRIP_W, H], radius=16, fill=DARK)

    f_brand = _font(12, bold=True)
    f_tiny = _font(9)
    f_small = _font(11)

    trophy_img = None
    if trophy_path and Path(trophy_path).is_file():
        try:
            tr = Image.open(trophy_path).convert('RGBA')
            # Fit trophy tall in strip (almost full height of upper strip)
            max_w, max_h = STRIP_W - 10, 280
            tr.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            # Optional: clear pure white corners for cleaner look on dark strip
            pixels = list(tr.getdata())
            cleaned = []
            for r, g, b, a in pixels:
                if r > 245 and g > 245 and b > 245:
                    cleaned.append((255, 255, 255, 0))
                else:
                    cleaned.append((r, g, b, a))
            tr.putdata(cleaned)
            trophy_img = tr
        except Exception:
            trophy_img = _load_logo(trophy_path, (STRIP_W - 20, 180))

    if trophy_img:
        tx = (STRIP_W - trophy_img.width) // 2
        ty_img = 12
        base.paste(trophy_img, (tx, ty_img), trophy_img)
        text_y = ty_img + trophy_img.height + 8
    else:
        text_y = 40

    # Keep brand text readable under trophy
    if text_y > H - 100:
        text_y = H - 95
    draw.text((18, text_y), 'PATHARI', fill=GOLD, font=f_brand)
    draw.text((12, text_y + 16), 'GOLD CUP', fill=GOLD_LIGHT, font=f_brand)
    draw.text((28, text_y + 36), '2026', fill=GOLD, font=f_small)
    draw.line([(16, text_y + 54), (STRIP_W - 16, text_y + 54)], fill=GOLD, width=2)
    draw.text((12, H - 48), 'Football Unites', fill=GOLD_LIGHT, font=f_tiny)
    draw.text((18, H - 34), 'Our Community', fill=GOLD_LIGHT, font=f_tiny)

    f_title = _font(26, bold=True)
    f_sub = _font(12)
    title = 'PATHARI GOLD CUP'
    bbox = draw.textbbox((0, 0), title, font=f_title)
    tw = bbox[2] - bbox[0]
    center_mid = 155 + (W - 280 - 155) / 2
    draw.text((center_mid - tw / 2, 22), title, fill=WHITE, font=f_title)
    sub = 'FOOTBALL TOURNAMENT'
    bbox = draw.textbbox((0, 0), sub, font=f_sub)
    sw = bbox[2] - bbox[0]
    draw.text((center_mid - sw / 2, 54), sub, fill=GOLD, font=f_sub)

    home_full = (home_team.name if home_team else 'HOME') or 'HOME'
    away_full = (away_team.name if away_team else 'AWAY') or 'AWAY'

    logo_y = 95
    left_x, right_x = 230, 540
    s = 96
    home_logo = _load_logo(home_logo_path, (s, s))
    away_logo = _load_logo(away_logo_path, (s, s))

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

    f_vs = _font(28, bold=True)
    draw.text((400, 125), 'VS', fill=GOLD_LIGHT, font=f_vs)

    f_team = _font(13, bold=True)
    for name, cx in ((home_full.upper(), left_x + s // 2), (away_full.upper(), right_x + s // 2)):
        bbox = draw.textbbox((0, 0), name, font=f_team)
        nw = bbox[2] - bbox[0]
        draw.text((cx - nw / 2, logo_y + s + 6), name, fill=WHITE, font=f_team)

    f_meta = _font(13)
    f_meta_b = _font(13, bold=True)
    f_tiny2 = _font(10)
    meta_y = 230
    if match and match.match_date:
        dt = match.match_date
        date_str = dt.strftime('%d %b %Y').upper()
        day_str = dt.strftime('(%A)')
        time_str = dt.strftime('%I:%M %p')
    else:
        date_str, day_str, time_str = 'TBD', '', 'TBD'

    venue = (match.venue if match else 'Pathari, Morang') or 'Pathari, Morang'
    venue_d = (match.venue_detail if match else '') or ''

    draw.text((185, meta_y), f'{date_str}  {day_str}', fill=WHITE, font=f_meta)
    draw.text((430, meta_y), f'{time_str}  Kick-off', fill=WHITE, font=f_meta)
    draw.text((185, meta_y + 26), f'{venue}', fill=WHITE, font=f_meta)
    if venue_d:
        draw.text((185, meta_y + 48), f'({venue_d})', fill=(180, 210, 180), font=f_tiny2)

    cls_name = (ticket_class.name if ticket_class else 'General') or 'General'
    gate = (ticket_class.gate if ticket_class else 'Gate 1') or 'Gate 1'
    zone = (ticket_class.zone if ticket_class else 'East Stand') or 'East Stand'
    price = float(ticket_class.price) if ticket_class else 0
    code = ticket.ticket_code if ticket else 'PGC-TKT-XXXX'

    chip_y = 318
    badge_w = max(90, 14 + len(cls_name) * 9)
    draw.rounded_rectangle([185, chip_y, 185 + badge_w, chip_y + 34], radius=8, fill=GOLD)
    f_badge = _font(13, bold=True)
    bbox = draw.textbbox((0, 0), cls_name.upper(), font=f_badge)
    bw = bbox[2] - bbox[0]
    draw.text((185 + (badge_w - bw) / 2, chip_y + 8), cls_name.upper(), fill=DARK, font=f_badge)

    col1 = 185 + badge_w + 20
    col2 = col1 + 110
    col3 = col2 + 130
    draw.text((col1, chip_y + 2), 'GATE', fill=(170, 180, 190), font=f_tiny2)
    draw.text((col1, chip_y + 16), str(gate), fill=WHITE, font=f_meta_b)
    draw.text((col2, chip_y + 2), 'ZONE', fill=(170, 180, 190), font=f_tiny2)
    draw.text((col2, chip_y + 16), str(zone), fill=WHITE, font=f_meta_b)
    draw.text((col3, chip_y + 2), 'PRICE', fill=(170, 180, 190), font=f_tiny2)
    draw.text((col3, chip_y + 16), f'Rs. {price:.0f}', fill=GOLD_LIGHT, font=f_meta_b)

    if footer_credit:
        f_cred = _font(9)
        bbox = draw.textbbox((0, 0), footer_credit, font=f_cred)
        cw = bbox[2] - bbox[0]
        draw.text((center_mid - cw / 2, H - 22), footer_credit, fill=(160, 170, 180), font=f_cred)

    stub_x = W - 280
    draw.rounded_rectangle([stub_x, 10, W - 10, H - 10], radius=14, fill=(248, 250, 252))
    draw.rounded_rectangle([W - 68, 10, W - 10, H - 10], radius=12, fill=DARK)
    draw.rectangle([W - 68, 10, W - 48, H - 10], fill=DARK)
    for yy in range(28, H - 28, 12):
        draw.line([(stub_x - 2, yy), (stub_x - 2, yy + 6)], fill=(200, 200, 210), width=2)

    f_stub = _font(11, bold=True)
    draw.text((stub_x + 22, 28), 'TICKET ID', fill=(100, 110, 120), font=f_tiny2)
    draw.text((stub_x + 22, 44), code, fill=NAVY, font=f_stub)

    payload = ticket.qr_payload if ticket and ticket.qr_payload else code
    qr = qrcode.QRCode(version=1, box_size=4, border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color='black', back_color='white').convert('RGB')
    qr_img = qr_img.resize((128, 128), Image.Resampling.NEAREST)
    base.paste(qr_img, (stub_x + 42, 78))

    draw.rounded_rectangle([stub_x + 28, 225, stub_x + 178, 256], radius=6, fill=NAVY)
    draw.text((stub_x + 46, 233), 'SCAN AT GATE', fill=WHITE, font=f_stub)
    draw.text((stub_x + 38, 270), 'One ticket = One entry', fill=(120, 130, 140), font=f_tiny2)
    draw.text((stub_x + 22, H - 48), code, fill=(80, 90, 100), font=f_tiny2)

    f_side = _font(10, bold=True)
    draw.text((W - 58, 90), cls_name.upper()[:6], fill=GOLD, font=f_side)
    bx = W - 54
    for i, hh in enumerate([16, 26, 12, 28, 18, 24, 14, 22, 10, 26, 16, 20]):
        draw.rectangle([bx, 190 + i * 8, bx + 3, 190 + i * 8 + max(4, hh // 3)], fill=GOLD)

    border = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle([2, 2, W - 3, H - 3], radius=18, outline=GOLD + (200,), width=3)
    base = Image.alpha_composite(base, border)

    out = io.BytesIO()
    base.convert('RGB').save(out, format='PNG', optimize=True)
    return out.getvalue()
