"""PDF wrapper around ticket PNG."""
import io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


def ticket_png_to_pdf(png_bytes: bytes, ticket_code: str = '') -> bytes:
    buf = io.BytesIO()
    # Landscape page sized for ticket
    page_w, page_h = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    img = ImageReader(io.BytesIO(png_bytes))
    # Fit ticket centered with margins
    margin = 15 * mm
    max_w = page_w - 2 * margin
    max_h = page_h - 2 * margin
    # Ticket aspect ~1200x420
    aspect = 1200 / 420
    if max_w / aspect <= max_h:
        tw, th = max_w, max_w / aspect
    else:
        th, tw = max_h, max_h * aspect
    x = (page_w - tw) / 2
    y = (page_h - th) / 2
    c.drawImage(img, x, y, width=tw, height=th, preserveAspectRatio=True, mask='auto')
    if ticket_code:
        c.setFont('Helvetica', 9)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawCentredString(page_w / 2, 10 * mm, ticket_code)
    c.showPage()
    c.save()
    return buf.getvalue()
