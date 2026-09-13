"""Meeting proposal + booking tools.

Deterministic and self-contained so the whole flow runs offline. Bookings are
recorded in an in-memory store and surfaced via the API, so a demo can show a
real, captured booking. This is designed to be swapped for a real calendar
(e.g. Outlook / Google / Calendly) later — replace ``book_meeting`` internals.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import asdict, dataclass, field
from typing import Dict, List
from zoneinfo import ZoneInfo


@dataclass
class Booking:
    name: str
    when: str
    email: str
    topic: str
    created_at: str


_BOOKINGS: List[Booking] = []


def _next_weekdays(count: int, tz: ZoneInfo) -> List[_dt.datetime]:
    days: List[_dt.datetime] = []
    cursor = _dt.datetime.now(tz) + _dt.timedelta(days=1)
    while len(days) < count:
        if cursor.weekday() < 5:  # Mon-Fri
            days.append(cursor)
        cursor += _dt.timedelta(days=1)
    return days


def propose_meeting_times(timezone: str = "UTC") -> str:
    """Suggest three concrete meeting slots over the next few business days."""
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo("UTC")
    d1, d2, d3 = _next_weekdays(3, tz)
    slots = [
        d1.replace(hour=10, minute=0),
        d2.replace(hour=14, minute=0),
        d3.replace(hour=11, minute=0),
    ]
    lines = [f"  {i+1}. {s.strftime('%A %d %b, %H:%M %Z')}" for i, s in enumerate(slots)]
    return "Here are a few times that work:\n" + "\n".join(lines)


def book_meeting(name: str, when: str, email: str = "", topic: str = "intro call") -> str:
    """Record a booked meeting and return a confirmation."""
    if not (when or "").strip():
        return "I need a specific time to book. Which of the proposed slots works?"
    booking = Booking(
        name=name or "there",
        when=when.strip(),
        email=email.strip(),
        topic=(topic or "intro call").strip(),
        created_at=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    )
    _BOOKINGS.append(booking)
    who = f"{booking.name}" + (f" ({booking.email})" if booking.email else "")
    return (
        f"✅ Meeting booked with {who} for {booking.when} — topic: {booking.topic}. "
        f"A calendar invite would be sent next. (Booking #{len(_BOOKINGS)})"
    )


def list_bookings() -> List[Dict]:
    return [asdict(b) for b in _BOOKINGS]


def clear_bookings() -> None:
    _BOOKINGS.clear()
