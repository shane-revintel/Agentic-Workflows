"""Inbound-revenue tools.

These implement the operational core of an inbound motion: triage and score a
lead, qualify it, draft the outreach that books a meeting, and forecast the
revenue those meetings produce. Every function is deterministic so the whole
flow runs offline with no API keys; the same tools are exposed to the LLM for
natural-language use, and can later be backed by real data (e.g. ZoomInfo for
enrichment/scoring, Outlook/CRM for scheduling).
"""

from __future__ import annotations

from typing import Optional

# --- parsing helpers -------------------------------------------------------


def _to_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "").replace("$", "").strip()))
    except (ValueError, TypeError):
        return None


def _to_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return None


def _to_rate(value) -> Optional[float]:
    """Accept '0.3', '30', or '30%' and return a fraction in [0, 1]."""
    if value is None or value == "":
        return None
    raw = str(value).strip()
    is_percent = raw.endswith("%")
    num = _to_float(raw.rstrip("%"))
    if num is None:
        return None
    if is_percent or num > 1:
        num = num / 100.0
    return max(0.0, min(1.0, num))


def _is_yes(value) -> bool:
    return str(value).strip().lower() in {"yes", "y", "true", "1", "high", "have", "confirmed"}


def _money(amount: float) -> str:
    return f"${amount:,.0f}"


# --- score_lead ------------------------------------------------------------

_SENIORITY = [
    (95, ("chief", "cxo", "ceo", "cfo", "cmo", "cto", "coo", "founder", "owner", "president")),
    (85, ("vp", "vice president", "svp", "evp", "head of")),
    (70, ("director",)),
    (55, ("manager", "lead", "principal")),
]

_SOURCE_SCORES = {
    "demo": 95,
    "pricing": 90,
    "referral": 88,
    "contact": 75,
    "event": 70,
    "webinar": 60,
    "content": 55,
    "ebook": 50,
    "newsletter": 35,
}


def score_lead(title: str, company_size="", source: str = "", signal: str = "") -> str:
    """Score an inbound lead by ICP fit + source intent and recommend a next action."""
    title_l = (title or "").lower()
    person = 35
    for score, keywords in _SENIORITY:
        if any(k in title_l for k in keywords):
            person = score
            break

    size = _to_int(company_size)
    if size is None:
        account = 50
    elif size >= 1000:
        account = 90
    elif size >= 200:
        account = 80
    elif size >= 50:
        account = 65
    elif size >= 10:
        account = 50
    else:
        account = 35

    src = (source or "").lower()
    src_score = max((v for k, v in _SOURCE_SCORES.items() if k in src), default=50)
    trigger = 75 if (signal or "").strip() else 40

    score = round(0.30 * person + 0.30 * account + 0.25 * src_score + 0.15 * trigger)
    if score >= 70:
        tier, sla, action = (
            "Hot",
            "Contact within 5 minutes",
            "Call now and offer to book a meeting today.",
        )
    elif score >= 45:
        tier, sla, action = (
            "Warm",
            "Contact within 1 business day",
            "Send a personalized email proposing two meeting times.",
        )
    else:
        tier, sla, action = (
            "Cold",
            "Add to a nurture sequence",
            "Enroll in an educational drip and re-score on the next engagement.",
        )

    return (
        f"Lead score: {score}/100 — {tier}\n"
        f"  • Person fit: {person}  • Account fit: {account}  "
        f"• Source intent: {src_score}  • Trigger: {trigger}\n"
        f"  • SLA: {sla}\n"
        f"  • Next action: {action}"
    )


# --- qualify_lead ----------------------------------------------------------


def qualify_lead(budget="", authority="", need="", timeline="") -> str:
    """BANT qualification. Pass yes/no (or a short value) for each dimension."""
    checks = {
        "Budget": _is_yes(budget),
        "Authority": _is_yes(authority),
        "Need": _is_yes(need),
        "Timeline": _is_yes(timeline),
    }
    met = sum(checks.values())
    lines = [f"  • {name}: {'✓' if ok else '✗'}" for name, ok in checks.items()]
    if met == 4:
        verdict = "Sales-ready — route to an AE and book a meeting now."
    elif met >= 2:
        verdict = "Promising — book a discovery call to close the gaps."
    else:
        verdict = "Not ready — nurture until more BANT criteria are met."
    return f"BANT qualification: {met}/4 met\n" + "\n".join(lines) + f"\n  • Verdict: {verdict}"


# --- forecast_revenue ------------------------------------------------------


def forecast_revenue(leads="", meeting_rate="", close_rate="", acv="") -> str:
    """Project meetings booked and revenue from an inbound lead volume."""
    n_leads = _to_float(leads)
    m_rate = _to_rate(meeting_rate)
    c_rate = _to_rate(close_rate)
    deal_value = _to_float(acv)
    missing = [
        name
        for name, val in (
            ("leads", n_leads),
            ("meeting_rate", m_rate),
            ("close_rate", c_rate),
            ("acv", deal_value),
        )
        if val is None
    ]
    if missing:
        return (
            "I need these to forecast: " + ", ".join(missing) + ". "
            "Example: forecast: leads=200 meeting_rate=30% close_rate=25% acv=12000"
        )

    meetings = n_leads * m_rate
    deals = meetings * c_rate
    revenue = deals * deal_value
    per_lead = revenue / n_leads if n_leads else 0
    return (
        f"Inbound revenue forecast\n"
        f"  • Leads: {n_leads:,.0f}\n"
        f"  • Meetings booked: {meetings:,.0f} ({m_rate:.0%} of leads)\n"
        f"  • Deals won: {deals:,.1f} ({c_rate:.0%} of meetings)\n"
        f"  • Projected revenue: {_money(revenue)} (ACV {_money(deal_value)})\n"
        f"  • Value per lead: {_money(per_lead)}"
    )


# --- draft_email -----------------------------------------------------------

_EMAIL_TEMPLATES = {
    "meeting_request": (
        "Quick idea for {company}",
        "Hi {name},\n\nThanks for your interest in what we're building. Teams like "
        "{company} usually want to move faster on {context} — I'd love to show you how "
        "in a focused 20-minute call.\n\nAre you open to Tuesday 10:00 or Wednesday "
        "14:00? I'll send an invite.\n\nBest,\n{sender}",
    ),
    "follow_up": (
        "Following up — {company}",
        "Hi {name},\n\nCircling back on {context}. I put together a couple of ideas "
        "specific to {company} and can walk you through them quickly.\n\nWould a short "
        "call this week work? Happy to fit your calendar.\n\nBest,\n{sender}",
    ),
    "recap": (
        "Recap & next steps — {company}",
        "Hi {name},\n\nGreat speaking today. To recap {context}, here are the next "
        "steps we agreed on. I'll get started on my side and propose a follow-up so "
        "{company} keeps momentum.\n\nBest,\n{sender}",
    ),
}


def draft_email(
    name: str, company: str = "your team", purpose: str = "meeting_request",
    context: str = "your goals", sender: str = "Your Name",
) -> str:
    """Draft a short, personalized outreach email that drives to a booked meeting."""
    key = (purpose or "meeting_request").strip().lower().replace(" ", "_")
    subject, body = _EMAIL_TEMPLATES.get(key, _EMAIL_TEMPLATES["meeting_request"])
    filled_subject = subject.format(company=company)
    filled_body = body.format(
        name=name or "there", company=company, context=context, sender=sender
    )
    return f"Subject: {filled_subject}\n\n{filled_body}"
