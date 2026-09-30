
"""Allocate and recycle ticket codes."""
from __future__ import annotations
from datetime import datetime, timezone
from app.utils.timeutil import now_nepal_naive
from app.extensions import db
from app.models.booking import Ticket
from app.models.ticket_code_pool import TicketCodePool


def _year():
    return datetime.now().year


def _parse_seq(code: str):
    """PGC-TKT-2026-000001 -> 1"""
    try:
        return int(code.rsplit('-', 1)[-1])
    except Exception:
        return None


def next_sequential_code():
    """Next code after highest existing ticket number for current year."""
    year = _year()
    prefix = f'PGC-TKT-{year}-'
    # max among live tickets
    live = Ticket.query.filter(Ticket.ticket_code.like(f'{prefix}%')).all()
    max_seq = 0
    for t in live:
        s = _parse_seq(t.ticket_code)
        if s is not None and s > max_seq:
            max_seq = s
    return f'{prefix}{max_seq + 1:06d}'


def allocate_ticket_code():
    """
    Prefer recycled codes from pool (oldest first).
    Else next sequential after latest issued.
    """
    recycled = (
        TicketCodePool.query
        .order_by(TicketCodePool.freed_at.asc())
        .first()
    )
    if recycled:
        code = recycled.ticket_code
        db.session.delete(recycled)
        return code
    return next_sequential_code()


def recycle_ticket_code(code, holder=None, email=None):
    if not code:
        return
    # don't duplicate
    if TicketCodePool.query.filter_by(ticket_code=code).first():
        return
    # don't recycle if somehow still live
    if Ticket.query.filter_by(ticket_code=code).first():
        return
    db.session.add(TicketCodePool(
        ticket_code=code,
        previous_holder=holder,
        previous_email=email,
        freed_at=now_nepal_naive(),
    ))
