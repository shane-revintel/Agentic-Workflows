"""Lead source.

Leads are modeled on Bowtie / Salesbot.io output: an enriched contact plus a
"fit reason" and score explaining why they match your ICP.

Two ways to get real leads in, in order of how easy they are:

1. **CSV import** (no API key): export your leads from Salesbot.io / Bowtie and
   upload the file (UI button or ``POST /api/leads/import``). The parser maps
   common column names automatically. Imported leads are saved to
   ``backend/data/leads.csv`` so they persist across restarts.
2. **API** (later): plug Bowtie's API into ``fetch_from_bowtie`` (guarded by
   ``BOWTIE_API_KEY``).

Until you import anything, a small sample set keeps the app runnable.
"""

from __future__ import annotations

import csv
import io
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEADS_CSV = DATA_DIR / "leads.csv"


@dataclass
class Lead:
    id: str
    name: str
    title: str
    company: str
    industry: str = ""
    email: str = ""
    source: str = "Salesbot.io (Bowtie)"
    fit_reason: str = ""
    fit_score: int = 0
    notes: str = ""

    def as_dict(self) -> Dict:
        return asdict(self)

    def context_block(self) -> str:
        """A compact briefing the SDR agent can use to personalize outreach."""
        parts = [
            f"Name: {self.name}",
            f"Title: {self.title}",
            f"Company: {self.company}" + (f" ({self.industry})" if self.industry else ""),
        ]
        if self.fit_reason:
            parts.append(f"Why they fit (from {self.source}): {self.fit_reason}")
        if self.fit_score:
            parts.append(f"Fit score: {self.fit_score}/100")
        if self.notes:
            parts.append(f"Notes: {self.notes}")
        return "\n".join(parts)


SAMPLE_LEADS: List[Lead] = [
    Lead(
        id="l1",
        name="Jordan Lee",
        title="Head of Growth",
        company="Northstar Retail",
        industry="E-commerce",
        email="jordan.lee@northstarretail.example",
        fit_reason=(
            "Fast-growing DTC brand scaling paid acquisition; likely struggling to "
            "respond to and qualify inbound leads quickly enough."
        ),
        fit_score=88,
    ),
    Lead(
        id="l2",
        name="Priya Shah",
        title="VP of Sales",
        company="Apex Logistics",
        industry="Supply chain SaaS",
        email="priya.shah@apexlogistics.example",
        fit_reason=(
            "Mid-market SaaS with a growing SDR team; hiring reps signals pressure "
            "to book more meetings without adding headcount."
        ),
        fit_score=82,
    ),
    Lead(
        id="l3",
        name="Marcus Reed",
        title="Founder & CEO",
        company="BrightHVAC",
        industry="Home services",
        email="marcus@brighthvac.example",
        fit_reason=(
            "Owner-operator generating inbound web leads but no dedicated SDR; "
            "high risk of slow follow-up losing deals to competitors."
        ),
        fit_score=76,
    ),
]

# --- flexible CSV column mapping ------------------------------------------

def _norm(header: str) -> str:
    return "".join(ch for ch in header.lower() if ch.isalnum())


# Map normalized header -> Lead field. First match wins per field.
_FIELD_ALIASES: Dict[str, List[str]] = {
    "name": ["name", "fullname", "contactname", "contact", "leadname", "person"],
    "first": ["firstname", "first", "givenname"],
    "last": ["lastname", "last", "surname", "familyname"],
    "title": ["title", "jobtitle", "position", "role"],
    "company": ["company", "companyname", "account", "accountname", "organization", "employer"],
    "industry": ["industry", "sector", "vertical"],
    "email": ["email", "emailaddress", "workemail", "businessemail"],
    "fit_reason": ["fitreason", "reason", "whytheyfit", "whyfit", "qualification", "reasoning", "fit"],
    "fit_score": ["fitscore", "score", "relevancy", "relevancyscore", "leadscore"],
    "notes": ["notes", "note", "comments", "comment"],
}


def _build_header_index(fieldnames: List[str]) -> Dict[str, str]:
    """Map each Lead field to the actual CSV column name present."""
    normalized = {_norm(h): h for h in fieldnames if h}
    resolved: Dict[str, str] = {}
    for field, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                resolved[field] = normalized[alias]
                break
    return resolved


def _to_int(value: str) -> int:
    try:
        return int(float(str(value).strip().replace("%", "")))
    except (ValueError, TypeError):
        return 0


def parse_leads_csv(text: str) -> List[Lead]:
    """Parse a CSV export into Lead objects, mapping common headers."""
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    idx = _build_header_index(reader.fieldnames)

    leads: List[Lead] = []
    for i, row in enumerate(reader, start=1):
        def get(field: str) -> str:
            col = idx.get(field)
            return (row.get(col) or "").strip() if col else ""

        name = get("name")
        if not name:
            name = " ".join(p for p in [get("first"), get("last")] if p).strip()
        company = get("company")
        # Skip empty rows.
        if not name and not company and not get("email"):
            continue

        leads.append(
            Lead(
                id=f"lead{i}",
                name=name or "Unknown",
                title=get("title"),
                company=company or "Unknown",
                industry=get("industry"),
                email=get("email"),
                fit_reason=get("fit_reason"),
                fit_score=_to_int(get("fit_score")),
                notes=get("notes"),
            )
        )
    return leads


# --- current lead set (imported or sample) --------------------------------

_current: Optional[List[Lead]] = None


def _ensure_loaded() -> None:
    global _current
    if _current is not None:
        return
    if LEADS_CSV.exists():
        try:
            parsed = parse_leads_csv(LEADS_CSV.read_text(encoding="utf-8"))
            _current = parsed or list(SAMPLE_LEADS)
        except Exception:
            _current = list(SAMPLE_LEADS)
    else:
        _current = list(SAMPLE_LEADS)


def list_leads() -> List[Lead]:
    _ensure_loaded()
    return list(_current or [])


def get_lead(lead_id: Optional[str]) -> Lead:
    """Return a lead by id, defaulting to the first available lead."""
    leads = list_leads()
    if lead_id:
        for lead in leads:
            if lead.id == lead_id:
                return lead
    return leads[0]


def import_leads_from_csv(text: str) -> List[Lead]:
    """Parse, persist, and activate leads from an uploaded CSV export."""
    leads = parse_leads_csv(text)
    if not leads:
        raise ValueError(
            "No leads found. Make sure the CSV has a header row with at least a "
            "name (or first/last) and company column."
        )
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LEADS_CSV.write_text(text, encoding="utf-8")
    global _current
    _current = leads
    return leads


def using_imported_leads() -> bool:
    return LEADS_CSV.exists()


def clear_imported_leads() -> None:
    """Revert to the sample set (used by tests and 'reset')."""
    global _current
    if LEADS_CSV.exists():
        LEADS_CSV.unlink()
    _current = None


def bowtie_configured() -> bool:
    return bool(os.getenv("BOWTIE_API_KEY"))


def fetch_from_bowtie() -> List[Lead]:
    """Placeholder for the direct Bowtie / Salesbot.io API integration.

    When you have API access, map its qualified-contact fields onto :class:`Lead`
    here (guarded by ``BOWTIE_API_KEY``). Until then, CSV import is the supported
    path and this returns whatever is currently loaded.
    """
    # TODO: call the Bowtie API with BOWTIE_API_KEY and map results to Lead.
    return list_leads()
